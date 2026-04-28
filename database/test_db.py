#!/usr/bin/env python3
"""
xiaoV Factory — 数据库集成测试
测试 MES 核心表创建 + 时序数据库读写降采样
"""
import sys, os, json, sqlite3, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mes_schema_ddl import create_database, DB_PATH as MES_DB_PATH
from timeseries_db import TimeSeriesDB

PASS = 0
FAIL = 0

def test(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  ✅ {name}")
        PASS += 1
    else:
        print(f"  ❌ {name}")
        FAIL += 1

def clean_db(path):
    if os.path.exists(path):
        os.remove(path)

def test_mes_schema():
    print(f"\n{'='*50}")
    print("测试 MES 数据库 Schema")
    print('='*50)

    clean_db(MES_DB_PATH)
    create_database(MES_DB_PATH)

    conn = sqlite3.connect(MES_DB_PATH)
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in c.fetchall()]
    test(f"创建了 {len(tables)} 张表", len(tables) >= 70)

    # 验证核心表
    required_tables = [
        'org_company', 'org_department', 'org_work_center', 'employee',
        'equipment', 'equipment_category', 'material', 'product',
        'batch_record', 'batch_ferment_param', 'batch_feeding_record',
        'batch_cip_record', 'batch_sterilize_record',
        'route', 'route_step', 'product_bom',
        'qc_test_record', 'qc_test_detail', 'qc_standard',
        'maintain_record', 'maintain_plan_item', 'equipment_maintain_plan',
        'inventory', 'warehouse', 'storage_location',
        'work_order', 'sop_document',
        'deviation', 'nonconformance', 'change_management',
        'supplier', 'customer',
        'utility_system', 'purified_water_record', 'compressed_air_record',
        'steam_system_record', 'wastewater_record',
        'equipment_runtime', 'equipment_fault', 'equipment_calibration',
        'calibration_record', 'spare_part',
        'fermentation_formula', 'fermentation_formula_detail',
        'process_param_template',
        'employee_certification', 'employee_training', 'employee_shift',
        'sampling_record', 'stability_study',
        'batch_energy_consumption', 'batch_operation_log',
        'batch_dry_record', 'batch_extract_record', 'batch_mix_record',
        'batch_intermediate', 'batch_label', 'batch_tank_assignment',
        'material_category', 'material_supplier',
    ]
    for tbl in required_tables:
        test(f"核心表 {tbl} 存在", tbl in tables)

    # 验证索引
    c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
    idx_count = c.fetchone()[0]
    test(f"创建了 {idx_count} 个索引", idx_count > 10)

    # 验证种子数据
    c.execute("SELECT name FROM org_company WHERE code='XIAOV'")
    test("种子数据: xiaoV Company已初始化", c.fetchone() is not None)

    conn.close()
    return tables


def test_timeseries_db():
    print(f"\n{'='*50}")
    print("测试 时序数据库")
    print('='*50)

    clean_db('/tmp/test_timeseries.db')
    db = TimeSeriesDB('/tmp/test_timeseries.db')

    mid = db.register_metric("temperature", "℃", "发酵温度")
    test("注册指标成功", mid is not None)
    test("获取指标ID", db.get_metric_id("temperature") == mid)

    now = int(time.time() * 1000)
    for i in range(100):
        db.write("temperature", "fermenter-00", 36.0 + i * 0.05, {"unit": "℃"}, now - (100 - i) * 1000)

    test("写入原始数据", db.write_count == 100)

    results = db.query("temperature", "fermenter-00", agg='raw', limit=5)
    test("查询原始数据返回结果", len(results) == 5)

    for _ in range(3):
        db.downsampling()

    stats = db.stats()
    test("降采样后agg_1m有数据", stats['agg_1m'] > 0)
    test("降采样后agg_1h有数据", stats['agg_1h'] > 0)

    agg_results = db.query("temperature", "fermenter-00", agg='1m', limit=3)
    test("聚合查询返回avg/min/max", len(agg_results) > 0 and 'avg' in agg_results[0])

    for dev in [f"fermenter-{i:02d}" for i in range(5)]:
        for _ in range(10):
            db.write("temperature", dev, 36.0, {}, now)
    test("多设备写入", db.write_count > 100)

    n = db.backfill("temperature", "fermenter-00", [30, 31, 32, 33, 34], now - 3600000, 60000)
    test(f"数据补传 {n} 条", n == 5)

    db.purge_old_data()
    return db


def test_integration():
    print(f"\n{'='*50}")
    print("集成测试: MES + 时序数据库")
    print('='*50)

    mes_db = sqlite3.connect(MES_DB_PATH)
    tsdb = TimeSeriesDB('/tmp/test_timeseries.db')

    # 直接插入批次，不依赖equipment_id外键
    mes_db.execute("INSERT OR IGNORE INTO org_company (code, name) VALUES ('XIAOV', 'xiaoV')")
    mes_db.execute("""
        INSERT OR IGNORE INTO batch_record (id, batch_no, product_id, status, batch_qty, created_at)
        VALUES (1, '20260427-F01', 1, 'RUNNING', 10000, datetime('now'))
    """)
    mes_db.commit()

    tsdb.write("temperature", "20260427-F01", 36.5, {"batch": "20260427-F01"})
    tsdb.write("ph", "20260427-F01", 6.8, {"batch": "20260427-F01"})

    result = tsdb.query("temperature", "20260427-F01", agg='raw', limit=1)
    test("批次关联时序数据查询成功", len(result) > 0)
    test("批次温度值正确", abs(result[0]['value'] - 36.5) < 0.001)

    mes_db.close()
    print(f"  场景: 批次 20260427-F01 ↔ 温度36.5℃ OK")


def test_purge():
    print(f"\n{'='*50}")
    print("测试 保留策略清理")
    print('='*50)

    db = TimeSeriesDB('/tmp/test_purge.db')

    old_ts = int(time.time() * 1000) - 8 * 24 * 3600 * 1000
    for i in range(10):
        db.write("temperature", "old-device", 20 + i, {}, old_ts + i * 1000)

    now = int(time.time() * 1000)
    for i in range(10):
        db.write("temperature", "new-device", 30 + i, {}, now - i * 1000)

    db.purge_old_data()
    test("保留策略清理不报错", True)


if __name__ == '__main__':
    print("=" * 50)
    print("  xiaoV Factory · 数据库系统测试")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    test_mes_schema()
    test_timeseries_db()
    test_integration()
    test_purge()

    print(f"\n{'='*50}")
    print(f"测试总结: ✅ {PASS} 通过  ❌ {FAIL} 失败")
    print(f"总测试数: {PASS + FAIL}")
    print('='*50)

    for p in ['/tmp/test_timeseries.db', '/tmp/test_purge.db']:
        if os.path.exists(p):
            os.remove(p)
