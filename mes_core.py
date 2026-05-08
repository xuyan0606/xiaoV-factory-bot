"""
MES Core Database — 酶制剂工厂
工单 / 批次 / 质检 / 设备 / 告警

SQLite，轻量，适合工厂内网部署
"""

import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from flask import Flask, jsonify, request, g
from functools import wraps
import threading

DB_PATH = "/Users/xuyan/software/hermesWorkspace/mes.db"

# ─────────────────────────────────────────────
# 数据库初始化
# ─────────────────────────────────────────────

def init_db():
    with get_db() as db:
        db.executescript("""
        -- 工单表
        CREATE TABLE IF NOT EXISTS production_orders (
            order_id    TEXT PRIMARY KEY,   -- PO-YYYYMMDD-XXX
            product_code TEXT NOT NULL,    -- 酶制剂品号，如 ENZYME-001
            product_name TEXT NOT NULL,
            batch_size   REAL NOT NULL,     -- kg
            fermenter_id TEXT,              -- 发酵罐编号
            plan_start  TEXT,
            plan_end    TEXT,
            status      TEXT DEFAULT 'pending',  -- pending / in_progress / completed / cancelled
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            priority    INTEGER DEFAULT 2  -- 1=紧急 2=普通 3=低
        );

        -- 批次追踪表
        CREATE TABLE IF NOT EXISTS batches (
            batch_id    TEXT PRIMARY KEY,  -- BAT-YYYYMMDD-XXX
            order_id    TEXT NOT NULL,
            stage       TEXT DEFAULT 'pending',  -- pending/sterilization/seed/fermentation/
                                                 -- centrifugation/drying/packaging/completed
            stage_index INTEGER DEFAULT 0,
            start_time  TEXT,
            end_time    TEXT,
            current_temp REAL,
            current_pH  REAL,
            current_DO  REAL,              -- 溶解氧 %
            FOREIGN KEY (order_id) REFERENCES production_orders(order_id)
        );

        -- 批次工艺参数历史
        CREATE TABLE IF NOT EXISTS batch_params (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id    TEXT NOT NULL,
            timestamp   TEXT DEFAULT (datetime('now')),
            temp        REAL,
            pH          REAL,
            DO          REAL,
            stir_speed  REAL,              -- 转速 rpm
            pressure    REAL,              -- 罐压 bar
            FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
        );

        -- 质量检验表
        CREATE TABLE IF NOT EXISTS quality_tests (
            test_id     TEXT PRIMARY KEY,  -- QC-YYYYMMDD-XXX
            batch_id    TEXT NOT NULL,
            stage       TEXT NOT NULL,     -- in_process / final_product / incoming
            enzyme_activity REAL,           -- 酶活 U/g
            moisture    REAL,              -- 水分 %
            microbial_count INTEGER,       -- 微生物总数 CFU/g
            pH_value    REAL,              -- pH值
            appearance  TEXT,              -- 外观
            result      TEXT DEFAULT 'pending',  -- pass / fail / warning / pending
            result_detail TEXT,             -- 超限详情 JSON: [{"param":"酶活","value":1800,"lo":2000,"hi":null,"unit":"U/g"},...]
            reviewed_by TEXT,               -- 审核人
            reviewed_at TEXT,              -- 审核时间
            review_remark TEXT,            -- 审核备注
            tester      TEXT,
            test_time   TEXT DEFAULT (datetime('now')),
            remark      TEXT,
            FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
        );

        -- 质量标准表
        CREATE TABLE IF NOT EXISTS quality_specs (
            standard_id TEXT PRIMARY KEY,  -- SPEC-YYYYMMDD-XXX
            product_type TEXT NOT NULL,    -- 产品类型，如 ENZYME-001 / all
            stage       TEXT NOT NULL,     -- in_process / final_product / incoming / all
            param_name  TEXT NOT NULL,     -- 参数名称：enzyme_activity / moisture / microbial_count / pH_value / appearance
            lo          REAL,               -- 下限（null表示不设下限）
            hi          REAL,               -- 上限（null表示不设上限）
            unit        TEXT,               -- 单位
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        -- 设备台账表
        CREATE TABLE IF NOT EXISTS equipment (
            equip_id    TEXT PRIMARY KEY,  -- FER-01 / CENT-01 等
            equip_name  TEXT NOT NULL,
            equip_type  TEXT NOT NULL,     -- fermenter / centrifuge / dryer / sterilizer
            model       TEXT,
            location    TEXT,
            status      TEXT DEFAULT 'idle',  -- idle / running / maintenance / fault
            last_maint  TEXT,
            next_maint  TEXT,
            install_date TEXT
        );

        -- 维保计划表
        CREATE TABLE IF NOT EXISTS maintenance_plan (
            plan_id        TEXT PRIMARY KEY,  -- MPLAN-YYYYMMDD-XXX
            equip_id       TEXT NOT NULL,
            maintenance_type TEXT NOT NULL,    -- routine / inspection / repair / calibration
            interval_days  INTEGER NOT NULL,  -- 维保周期天
            last_date      TEXT,              -- 上次维保日期
            next_date      TEXT NOT NULL,     -- 下次维保日期
            status         TEXT DEFAULT 'active',  -- active / inactive
            remark         TEXT,
            created_at     TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (equip_id) REFERENCES equipment(equip_id)
        );

        -- 维保记录表
        CREATE TABLE IF NOT EXISTS maintenance_record (
            record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id        TEXT,
            equip_id       TEXT NOT NULL,
            record_time    TEXT DEFAULT (datetime('now')),  -- 执行时间
            maintenance_type TEXT NOT NULL,  -- routine / inspection / repair / calibration
            executor       TEXT,              -- 执行人
            result         TEXT,              -- 保养结果: ok / issues / failed
            cost           REAL,              -- 费用元
            remark         TEXT,
            FOREIGN KEY (equip_id) REFERENCES equipment(equip_id),
            FOREIGN KEY (plan_id) REFERENCES maintenance_plan(plan_id)
        );

        -- 告警记录表
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id    TEXT,
            equip_id    TEXT,
            alert_type  TEXT NOT NULL,     -- temp_high / pH_low / DO_low / maintenance_due
            level       TEXT DEFAULT 'warning',  -- info / warning / critical
            message     TEXT NOT NULL,
            value       REAL,               -- 触发值
            threshold   REAL,               -- 阈值
            status      TEXT DEFAULT 'active',  -- active / acknowledged / resolved
            created_at  TEXT DEFAULT (datetime('now')),
            resolved_at TEXT,
            FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
            FOREIGN KEY (equip_id) REFERENCES equipment(equip_id)
        );

        -- 报工记录表（工单执行反馈：投料、产出、得率）
        CREATE TABLE IF NOT EXISTS work_reports (
            work_report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id    TEXT,
            order_id    TEXT NOT NULL,
            worker      TEXT,
            report_time TEXT DEFAULT (datetime('now')),
            stage       TEXT,              -- 报工时所在工序阶段
            input_amount REAL DEFAULT 0,  -- 实际投入 kg
            output_amount REAL DEFAULT 0, -- 实际产出 kg
            yield_rate  REAL,              -- 得率 % = output/input*100
            status      TEXT DEFAULT 'recorded',  -- recorded / confirmed / cancelled
            remark      TEXT,
            FOREIGN KEY (order_id) REFERENCES production_orders(order_id),
            FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
        );

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_batches_order ON batches(order_id);
        CREATE INDEX IF NOT EXISTS idx_batches_stage ON batches(stage);
        CREATE INDEX IF NOT EXISTS idx_quality_batch ON quality_tests(batch_id);
        CREATE INDEX IF NOT EXISTS idx_quality_spec_lookup ON quality_specs(product_type, stage);
        CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
        CREATE INDEX IF NOT EXISTS idx_batch_params_time ON batch_params(batch_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_maint_equip ON maintenance_plan(equip_id);
        CREATE INDEX IF NOT EXISTS idx_maint_plan_status ON maintenance_plan(next_date, status);
        CREATE INDEX IF NOT EXISTS idx_mrec_equip ON maintenance_record(equip_id);
        CREATE INDEX IF NOT EXISTS idx_mrec_plan ON maintenance_record(plan_id);
        CREATE INDEX IF NOT EXISTS idx_work_reports_order ON work_reports(order_id);
        CREATE INDEX IF NOT EXISTS idx_work_reports_batch ON work_reports(batch_id);

        -- 用户表（认证）
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name    TEXT,
            role         TEXT NOT NULL DEFAULT 'operator',  -- admin / manager / operator / viewer
            department   TEXT,   -- 发酵车间 / 质检 / 设备 / 仓库
            phone        TEXT,
            status       TEXT DEFAULT 'active',
            created_at   TEXT DEFAULT (datetime('now'))
        );

        -- 操作审计日志
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            action      TEXT NOT NULL,
            resource    TEXT,
            resource_id TEXT,
            detail      TEXT,
            ip          TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- 班次管理表
        CREATE TABLE IF NOT EXISTS shifts (
            shift_id    TEXT PRIMARY KEY,
            shift_date  TEXT NOT NULL,
            shift_type  TEXT NOT NULL,
            leader      TEXT,
            start_time  TEXT,
            end_time    TEXT,
            status      TEXT DEFAULT 'active',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- 交接班记录表
        CREATE TABLE IF NOT EXISTS handover_records (
            record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id_out    TEXT,
            shift_id_in     TEXT,
            handover_time   TEXT DEFAULT (datetime('now')),
            handover_type   TEXT NOT NULL,
            content         TEXT,
            issues          TEXT,
            attachments     TEXT,
            status          TEXT DEFAULT 'pending',
            confirmed_by    TEXT,
            confirmed_at    TEXT,
            created_by      TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_shifts_date ON shifts(shift_date);
        CREATE INDEX IF NOT EXISTS idx_shifts_status ON shifts(status);
        CREATE INDEX IF NOT EXISTS idx_handover_shift_out ON handover_records(shift_id_out);
        CREATE INDEX IF NOT EXISTS idx_handover_shift_in ON handover_records(shift_id_in);
        CREATE INDEX IF NOT EXISTS idx_handover_time ON handover_records(handover_time);

        -- 启用 WAL 模式（提升并发读写性能）
        PRAGMA journal_mode=WAL;
        PRAGMA busy_timeout=5000;
        """)
        # 迁移旧 quality_tests 表（新增列，IF NOT EXISTS 防重）
        try:
            db.execute("ALTER TABLE quality_tests ADD COLUMN result_detail TEXT")
            db.execute("ALTER TABLE quality_tests ADD COLUMN reviewed_by TEXT")
            db.execute("ALTER TABLE quality_tests ADD COLUMN reviewed_at TEXT")
            db.execute("ALTER TABLE quality_tests ADD COLUMN review_remark TEXT")
        except Exception as e:
            if 'duplicate column' not in str(e): raise
        print("[MES] 数据库初始化完成")

# ─────────────────────────────────────────────
# 数据库连接上下文管理器
# ─────────────────────────────────────────────

def get_db():
    db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    return db

@contextmanager
def use_db():
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# ─────────────────────────────────────────────
# 工单 CRUD
# ─────────────────────────────────────────────

def create_order(product_code, product_name, batch_size, fermenter_id=None,
                 plan_start=None, plan_end=None, priority=2):
    order_id = f"PO-{datetime.now().strftime('%Y%m%d')}-{_seq('PO')}"
    with use_db() as db:
        db.execute("""
            INSERT INTO production_orders
            (order_id, product_code, product_name, batch_size, fermenter_id,
             plan_start, plan_end, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [order_id, product_code, product_name, batch_size, fermenter_id,
              plan_start, plan_end, priority])
    return order_id

def get_order(order_id):
    with use_db() as db:
        row = db.execute(
            "SELECT * FROM production_orders WHERE order_id = ?", [order_id]
        ).fetchone()
        return dict(row) if row else None

def list_orders(status=None, limit=50):
    with use_db() as db:
        if status:
            rows = db.execute(
                "SELECT * FROM production_orders WHERE status=? ORDER BY priority, created_at DESC LIMIT ?",
                [status, limit]
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM production_orders ORDER BY priority, created_at DESC LIMIT ?",
                [limit]
            ).fetchall()
        return [dict(r) for r in rows]

def update_order_status(order_id, status):
    with use_db() as db:
        db.execute(
            "UPDATE production_orders SET status=?, updated_at=datetime('now') WHERE order_id=?",
            [status, order_id]
        )

def report_order(order_id, operator, input_qty, output_qty=None, remark=None):
    """工单报工（兼容旧接口）"""
    with use_db() as db:
        batch_row = db.execute(
            "SELECT batch_id FROM batches WHERE order_id=? ORDER BY start_time DESC LIMIT 1",
            [order_id]
        ).fetchone()
        batch_id = batch_row['batch_id'] if batch_row else None
        yield_rate = None
        if output_qty and input_qty and input_qty > 0:
            yield_rate = round(output_qty / input_qty * 100, 2)
        db.execute("""
            INSERT INTO work_reports
            (order_id, batch_id, worker, stage, input_amount, output_amount, yield_rate, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [order_id, batch_id, operator, None, input_qty, output_qty, yield_rate, remark])

def create_work_report(order_id, batch_id, worker, report_time=None, stage=None,
                        input_amount=None, output_amount=None, yield_rate=None,
                        status='recorded', remark=None):
    """创建报工记录（投料、产出、得率记录）
    得率自动计算：yield_rate = output_amount / input_amount * 100
    """
    if report_time is None:
        report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 自动算得率
    if yield_rate is None and input_amount and output_amount and input_amount > 0:
        yield_rate = round(output_amount / input_amount * 100, 2)
    with use_db() as db:
        db.execute("""
            INSERT INTO work_reports
            (order_id, batch_id, worker, report_time, stage,
             input_amount, output_amount, yield_rate, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [order_id, batch_id, worker, report_time, stage,
              input_amount, output_amount, yield_rate, status, remark])

def list_work_reports(order_id=None, batch_id=None, worker=None,
                      status=None, date=None, limit=50):
    """查询报工记录列表，支持多条件过滤"""
    with use_db() as db:
        sql = """
            SELECT wr.*,
                   po.product_name, po.batch_size as target_yield,
                   b.stage as current_stage
            FROM work_reports wr
            LEFT JOIN production_orders po ON po.order_id = wr.order_id
            LEFT JOIN batches b ON b.batch_id = wr.batch_id
            WHERE 1=1
        """
        params = []
        if order_id:
            sql += " AND wr.order_id=?"
            params.append(order_id)
        if batch_id:
            sql += " AND wr.batch_id=?"
            params.append(batch_id)
        if worker:
            sql += " AND wr.worker=?"
            params.append(worker)
        if status:
            sql += " AND wr.status=?"
            params.append(status)
        if date:
            sql += " AND date(wr.report_time) = date(?)"
            params.append(date)
        sql += " ORDER BY wr.report_time DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def update_work_report(work_report_id, **kwargs):
    """更新报工记录（确认/取消）"""
    allowed = ['worker', 'stage', 'input_amount', 'output_amount',
               'yield_rate', 'status', 'remark']
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return None
    # 如果改了产出/投入，自动重算得率
    if 'output_amount' in fields or 'input_amount' in fields:
        with use_db() as db:
            row = db.execute(
                "SELECT input_amount, output_amount FROM work_reports WHERE work_report_id=?",
                [work_report_id]
            ).fetchone()
            if row:
                inp = fields.get('input_amount', row['input_amount'])
                out = fields.get('output_amount', row['output_amount'])
                if inp and out and inp > 0:
                    fields['yield_rate'] = round(out / inp * 100, 2)
    sets = ', '.join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [work_report_id]
    with use_db() as db:
        db.execute(f"UPDATE work_reports SET {sets} WHERE work_report_id=?", vals)
        row = db.execute(
            "SELECT * FROM work_reports WHERE work_report_id=?", [work_report_id]
        ).fetchone()
        return dict(row) if row else None

# ─────────────────────────────────────────────
# 批次管理
# ─────────────────────────────────────────────

STAGES = [
    "pending", "sterilization", "seed", "fermentation",
    "centrifugation", "drying", "packaging", "completed"
]

def create_batch(order_id):
    batch_id = f"BAT-{datetime.now().strftime('%Y%m%d')}-{_seq('BAT')}"
    with use_db() as db:
        db.execute(
            "INSERT INTO batches (batch_id, order_id, stage, stage_index) VALUES (?, ?, 'pending', 0)",
            [batch_id, order_id]
        )
    return batch_id

def get_batch(batch_id):
    with use_db() as db:
        row = db.execute(
            "SELECT * FROM batches WHERE batch_id = ?", [batch_id]
        ).fetchone()
        return dict(row) if row else None

def advance_batch_stage(batch_id):
    """批次推进到下一阶段"""
    with use_db() as db:
        batch = db.execute("SELECT * FROM batches WHERE batch_id=?", [batch_id]).fetchone()
        if not batch: return None
        idx = batch['stage_index']
        if idx >= len(STAGES) - 1: return batch['stage']
        new_stage = STAGES[idx + 1]
        db.execute(
            "UPDATE batches SET stage=?, stage_index=?, end_time=datetime('now') WHERE batch_id=?",
            [new_stage, idx+1, batch_id]
        )
        # 如果进入发酵阶段，自动更新工单状态
        if new_stage == 'fermentation':
            db.execute(
                "UPDATE production_orders SET status='in_progress', updated_at=datetime('now') WHERE order_id=?",
                [batch['order_id']]
            )
        # 如果完成，自动完工工单
        if new_stage == 'completed':
            db.execute(
                "UPDATE production_orders SET status='completed', updated_at=datetime('now') WHERE order_id=?",
                [batch['order_id']]
            )
        return new_stage

def record_batch_params(batch_id, temp=None, pH=None, DO=None, stir_speed=None, pressure=None):
    """记录批次实时工艺参数"""
    with use_db() as db:
        db.execute("""
            INSERT INTO batch_params (batch_id, temp, pH, DO, stir_speed, pressure)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [batch_id, temp, pH, DO, stir_speed, pressure])
        db.execute("""
            UPDATE batches SET current_temp=?, current_pH=?, current_DO=? WHERE batch_id=?
        """, [temp, pH, DO, batch_id])

def list_batches(stage=None, limit=50):
    with use_db() as db:
        if stage:
            rows = db.execute(
                "SELECT * FROM batches WHERE stage=? ORDER BY start_time DESC LIMIT ?",
                [stage, limit]
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM batches ORDER BY start_time DESC LIMIT ?",
                [limit]
            ).fetchall()
        return [dict(r) for r in rows]

def get_batch_by_order(order_id):
    with use_db() as db:
        row = db.execute(
            "SELECT * FROM batches WHERE order_id=? ORDER BY start_time DESC LIMIT 1",
            [order_id]
        ).fetchone()
        return dict(row) if row else None

def get_batch_history(batch_id, limit=100, start_time=None, end_time=None):
    """获取批次历史参数，支持时间范围过滤"""
    with use_db() as db:
        sql = "SELECT * FROM batch_params WHERE batch_id=?"
        params = [batch_id]
        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time)
        sql += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# 质量管理
# ─────────────────────────────────────────────

def create_quality_spec(product_type, stage, param_name, lo=None, hi=None, unit=None):
    """新增质量标准"""
    standard_id = f"SPEC-{datetime.now().strftime('%Y%m%d')}-{_seq('SPEC')}"
    with use_db() as db:
        db.execute("""
            INSERT INTO quality_specs
            (standard_id, product_type, stage, param_name, lo, hi, unit)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [standard_id, product_type, stage, param_name, lo, hi, unit])
    return standard_id

def get_quality_spec(standard_id):
    with use_db() as db:
        row = db.execute("SELECT * FROM quality_specs WHERE standard_id=?", [standard_id]).fetchone()
        return dict(row) if row else None

def list_quality_specs(product_type=None, stage=None):
    """按产品类型+阶段筛选质量标准"""
    with use_db() as db:
        if product_type and stage:
            rows = db.execute(
                "SELECT * FROM quality_specs WHERE product_type IN (?, 'all') AND stage IN (?, 'all') ORDER BY product_type, stage",
                [product_type, stage]
            ).fetchall()
        elif product_type:
            rows = db.execute("SELECT * FROM quality_specs WHERE product_type IN (?, 'all') ORDER BY product_type, stage", [product_type]).fetchall()
        elif stage:
            rows = db.execute("SELECT * FROM quality_specs WHERE stage IN (?, 'all') ORDER BY product_type, stage", [stage]).fetchall()
        else:
            rows = db.execute("SELECT * FROM quality_specs ORDER BY product_type, stage").fetchall()
        return [dict(r) for r in rows]

def check_quality_spec(product_type, stage):
    """按批次产品类型+阶段匹配质量标准，返回规格字典"""
    specs = list_quality_specs(product_type=product_type, stage=stage)
    return {s['param_name']: s for s in specs}

def create_quality_test(batch_id, stage, tester, **kwargs):
    test_id = f"QC-{datetime.now().strftime('%Y%m%d')}-{_seq('QC')}"
    with use_db() as db:
        db.execute("""
            INSERT INTO quality_tests
            (test_id, batch_id, stage, tester, enzyme_activity, moisture,
             microbial_count, pH_value, appearance, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            test_id, batch_id, stage, tester,
            kwargs.get('enzyme_activity'),
            kwargs.get('moisture'),
            kwargs.get('microbial_count'),
            kwargs.get('pH_value'),
            kwargs.get('appearance'),
            kwargs.get('remark')
        ])
    return test_id

def judge_quality(test_id):
    """根据质量标准自动判定检验结果
    返回: {'result': 'pass'/'fail'/'warning', 'details': [{'param':..., 'value':..., 'lo':..., 'hi':..., 'unit':...},...], 'test_id':...}
    """
    with use_db() as db:
        t = db.execute("SELECT * FROM quality_tests WHERE test_id=?", [test_id]).fetchone()
        if not t: return None

        # 获取批次产品类型
        batch = db.execute("SELECT b.*, po.product_code FROM batches b JOIN production_orders po ON b.order_id=po.order_id WHERE b.batch_id=?", [t['batch_id']]).fetchone()
        product_type = batch['product_code'] if batch else None

        # 匹配质量标准
        specs = check_quality_spec(product_type, t['stage']) if product_type else {}

        violations = []
        warnings = []

        # 检验参数
        test_params = {
            'enzyme_activity': {'value': t['enzyme_activity'], 'name': '酶活'},
            'moisture': {'value': t['moisture'], 'name': '水分'},
            'microbial_count': {'value': t['microbial_count'], 'name': '微生物'},
            'pH_value': {'value': t['pH_value'], 'name': 'pH值'},
            'appearance': {'value': t['appearance'], 'name': '外观'},
        }

        for param_key, param_info in test_params.items():
            val = param_info['value']
            if val is None:
                continue
            spec = specs.get(param_key)
            if not spec:
                continue

            lo = spec['lo']
            hi = spec['hi']
            unit = spec['unit'] or ''
            name = param_info['name']

            if lo is not None and val < lo:
                violations.append({'param': name, 'param_key': param_key, 'value': val, 'lo': lo, 'hi': hi, 'unit': unit, 'type': 'low'})
            elif hi is not None and val > hi:
                violations.append({'param': name, 'param_key': param_key, 'value': val, 'lo': lo, 'hi': hi, 'unit': unit, 'type': 'high'})
            elif lo is not None and hi is not None:
                # 有标准但未超限，接近边界(80%区间)则warning
                range_width = hi - lo
                if range_width > 0:
                    lower_warn = lo + range_width * 0.2
                    upper_warn = hi - range_width * 0.2
                    if val < lower_warn or val > upper_warn:
                        warnings.append({'param': name, 'param_key': param_key, 'value': val, 'lo': lo, 'hi': hi, 'unit': unit})

        # 判定逻辑
        if violations:
            result = 'fail'
        elif warnings:
            result = 'warning'
        else:
            result = 'pass'

        # 外观为文本，仅检查非空
        if t['appearance'] is None and specs.get('appearance'):
            pass  # 外观已在上面处理

        # 写入详情
        all_issues = violations + warnings
        result_detail = json.dumps(all_issues, ensure_ascii=False) if all_issues else None

        db.execute("""
            UPDATE quality_tests
            SET result=?, result_detail=?
            WHERE test_id=?
        """, [result, result_detail, test_id])

        return {'result': result, 'details': all_issues, 'test_id': test_id}

def review_quality_test(test_id, reviewed_by, result, review_remark=None):
    """人工审核覆盖自动判定结果"""
    with use_db() as db:
        t = db.execute("SELECT * FROM quality_tests WHERE test_id=?", [test_id]).fetchone()
        if not t: return None
        db.execute("""
            UPDATE quality_tests
            SET result=?, reviewed_by=?, reviewed_at=datetime('now'), review_remark=?
            WHERE test_id=?
        """, [result, reviewed_by, review_remark, test_id])
        updated = db.execute("SELECT * FROM quality_tests WHERE test_id=?", [test_id]).fetchone()
        return dict(updated)

def list_quality_tests(batch_id=None, result=None, limit=50):
    with use_db() as db:
        if batch_id:
            rows = db.execute(
                "SELECT * FROM quality_tests WHERE batch_id=? ORDER BY test_time DESC LIMIT ?",
                [batch_id, limit]
            ).fetchall()
        elif result:
            rows = db.execute(
                "SELECT * FROM quality_tests WHERE result=? ORDER BY test_time DESC LIMIT ?",
                [result, limit]
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM quality_tests ORDER BY test_time DESC LIMIT ?",
                [limit]
            ).fetchall()
        return [dict(r) for r in rows]

def seed_default_quality_specs():
    """写入酶制剂默认质量标准"""
    with use_db() as db:
        existing = db.execute("SELECT COUNT(*) FROM quality_specs").fetchone()[0]
        if existing > 0:
            return

    defaults = [
        # 成品阶段所有酶制剂产品
        ('all', 'final_product', 'enzyme_activity', 2000, None, 'U/g'),
        ('all', 'final_product', 'moisture', None, 8.0, '%'),
        ('all', 'final_product', 'microbial_count', None, 1000, 'CFU/g'),
        ('all', 'final_product', 'pH_value', 4.5, 7.0, ''),
        # 加工中阶段
        ('all', 'in_process', 'enzyme_activity', 1500, None, 'U/g'),
        ('all', 'in_process', 'moisture', None, 10.0, '%'),
        ('all', 'in_process', 'pH_value', 4.0, 7.5, ''),
        # 来料阶段
        ('all', 'incoming', 'microbial_count', None, 500, 'CFU/g'),
    ]
    for product_type, stage, param_name, lo, hi, unit in defaults:
        create_quality_spec(product_type, stage, param_name, lo, hi, unit)

# ─────────────────────────────────────────────
# 设备管理
# ─────────────────────────────────────────────

def create_equipment(equip_id, equip_name, equip_type, model=None, location=None):
    with use_db() as db:
        db.execute("""
            INSERT OR IGNORE INTO equipment (equip_id, equip_name, equip_type, model, location, install_date)
            VALUES (?, ?, ?, ?, ?, date('now'))
        """, [equip_id, equip_name, equip_type, model, location])

def get_equipment(equip_id):
    with use_db() as db:
        row = db.execute("SELECT * FROM equipment WHERE equip_id=?", [equip_id]).fetchone()
        return dict(row) if row else None

def list_equipment(equip_type=None, status=None):
    with use_db() as db:
        if equip_type and status:
            rows = db.execute(
                "SELECT * FROM equipment WHERE equip_type=? AND status=?",
                [equip_type, status]
            ).fetchall()
        elif equip_type:
            rows = db.execute(
                "SELECT * FROM equipment WHERE equip_type=?", [equip_type]
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM equipment").fetchall()
        return [dict(r) for r in rows]

def update_equip_status(equip_id, status):
    with use_db() as db:
        db.execute("UPDATE equipment SET status=? WHERE equip_id=?", [status, equip_id])

# ─────────────────────────────────────────────
# 维保计划管理
# ─────────────────────────────────────────────

# 维保周期（天）按设备类型
MAINTENANCE_CYCLES = {
    'fermenter': 30,
    'centrifuge': 60,
    'dryer': 90,
    'sterilizer': 90,
    'default': 90,
}

def get_maintenance_cycle(equip_type):
    return MAINTENANCE_CYCLES.get(equip_type, MAINTENANCE_CYCLES['default'])

# ─── 维保计划 CRUD ───

def _make_plan_id():
    return f"MPLAN-{datetime.now().strftime('%Y%m%d')}-{_seq('MPLAN')}"

def create_maintenance_plan(equip_id, maintenance_type, interval_days=None, last_date=None, next_date=None, remark=None):
    """在 maintenance_plan 表中创建计划，返回 plan_id"""
    plan_id = _make_plan_id()
    if interval_days is None:
        eq = get_equipment(equip_id)
        interval_days = get_maintenance_cycle(eq['equip_type']) if eq else 90
    if next_date is None and last_date:
        next_date = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=interval_days)).strftime('%Y-%m-%d')
    with use_db() as db:
        db.execute("""
            INSERT INTO maintenance_plan
            (plan_id, equip_id, maintenance_type, interval_days, last_date, next_date, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
        """, [plan_id, equip_id, maintenance_type, interval_days, last_date, next_date, remark])
    return plan_id

def get_maintenance_plan(plan_id):
    with use_db() as db:
        row = db.execute("SELECT * FROM maintenance_plan WHERE plan_id=?", [plan_id]).fetchone()
        return dict(row) if row else None

def list_maintenance_plans(equip_id=None, status=None):
    """列出维保计划，支持过滤"""
    with use_db() as db:
        sql = """
            SELECT mp.*, e.equip_name, e.equip_type, e.model, e.location
            FROM maintenance_plan mp
            JOIN equipment e ON mp.equip_id=e.equip_id
            WHERE 1=1
        """
        params = []
        if equip_id:
            sql += " AND mp.equip_id=?"
            params.append(equip_id)
        if status:
            sql += " AND mp.status=?"
            params.append(status)
        sql += " ORDER BY mp.next_date"
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def update_maintenance_plan(plan_id, **kwargs):
    """更新维保计划：interval_days, last_date, next_date, status, remark"""
    allowed = ['interval_days', 'last_date', 'next_date', 'status', 'remark']
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return None
    sets = ', '.join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [plan_id]
    with use_db() as db:
        db.execute(f"UPDATE maintenance_plan SET {sets} WHERE plan_id=?", vals)
        row = db.execute("SELECT * FROM maintenance_plan WHERE plan_id=?", [plan_id]).fetchone()
    return dict(row) if row else None

def auto_generate_plans():
    """
    根据设备类型自动生成维保计划。
    检查每台设备是否有 active 计划，没有则创建；过期则标记。
    返回创建的 plan_id 列表。
    """
    today = datetime.now().strftime('%Y-%m-%d')
    created = []
    with use_db() as db:
        equip_rows = db.execute("SELECT * FROM equipment").fetchall()
        for eq in equip_rows:
            eq = dict(eq)
            # 检查是否已有 active 计划
            existing = db.execute(
                "SELECT plan_id, next_date FROM maintenance_plan WHERE equip_id=? AND status='active' LIMIT 1",
                [eq['equip_id']]
            ).fetchone()
            if existing:
                # 检查是否已逾期
                if existing['next_date'] and existing['next_date'] < today:
                    db.execute(
                        "UPDATE maintenance_plan SET status='overdue' WHERE plan_id=?",
                        [existing['plan_id']]
                    )
                continue
            # 无 active 计划，创建新计划
            interval = get_maintenance_cycle(eq['equip_type'])
            # 计算下次维保日期
            if eq.get('next_maint'):
                last = eq.get('last_maint') or today
                next_d = eq['next_maint'] if eq['next_maint'] >= today else (
                    (datetime.strptime(last, '%Y-%m-%d') + timedelta(days=interval)).strftime('%Y-%m-%d')
                )
            else:
                start = eq.get('install_date') or today
                next_d = (datetime.strptime(start, '%Y-%m-%d') + timedelta(days=interval)).strftime('%Y-%m-%d')
            plan_id = _make_plan_id()
            status = 'overdue' if next_d < today else 'active'
            db.execute("""
                INSERT INTO maintenance_plan
                (plan_id, equip_id, maintenance_type, interval_days, last_date, next_date, status, remark)
                VALUES (?, ?, 'routine', ?, ?, ?, ?, ?)
            """, [plan_id, eq['equip_id'], interval, eq.get('last_maint'), next_d, status,
                  f"系统自动生成，周期{interval}天"])
            created.append(plan_id)
    return created

def get_overdue_maintenance():
    """返回逾期维保列表（next_date < today 且 status=active）"""
    today = datetime.now().strftime('%Y-%m-%d')
    with use_db() as db:
        rows = db.execute("""
            SELECT mp.*, e.equip_name, e.equip_type, e.model, e.location, e.status as equip_status
            FROM maintenance_plan mp
            JOIN equipment e ON mp.equip_id=e.equip_id
            WHERE mp.next_date < ? AND mp.status = 'active'
            ORDER BY mp.next_date
        """, [today]).fetchall()
        return [dict(r) for r in rows]

def get_upcoming_maintenance(days=7):
    """返回 days 天内即将到期的维保计划"""
    today = datetime.now().date()
    future = (today + timedelta(days=days)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    with use_db() as db:
        rows = db.execute("""
            SELECT mp.*, e.equip_name, e.equip_type, e.model, e.location
            FROM maintenance_plan mp
            JOIN equipment e ON mp.equip_id=e.equip_id
            WHERE mp.next_date BETWEEN ? AND ? AND mp.status = 'active'
            ORDER BY mp.next_date
        """, [today_str, future]).fetchall()
        return [dict(r) for r in rows]

# ─── 维保记录 CRUD ───

def create_maintenance_record(plan_id, equip_id, maintenance_type, executor=None, result=None, cost=None, remark=None):
    """创建维保执行记录，同时更新关联计划"""
    with use_db() as db:
        record_id = db.execute("""
            INSERT INTO maintenance_record
            (plan_id, equip_id, maintenance_type, executor, result, cost, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [plan_id, equip_id, maintenance_type, executor, result, cost, remark]).lastrowid
        # 更新关联计划：last_date=今天，next_date+=interval_days，状态变回 active
        if plan_id:
            plan = db.execute("SELECT * FROM maintenance_plan WHERE plan_id=?", [plan_id]).fetchone()
            if plan:
                next_d = (datetime.strptime(plan['next_date'], '%Y-%m-%d') + timedelta(days=plan['interval_days'])).strftime('%Y-%m-%d')
                db.execute("""
                    UPDATE maintenance_plan
                    SET last_date=?, next_date=?, status='active'
                    WHERE plan_id=?
                """, [datetime.now().strftime('%Y-%m-%d'), next_d, plan_id])
            # 更新设备台账
            db.execute(
                "UPDATE equipment SET last_maint=?, next_maint=? WHERE equip_id=?",
                [datetime.now().strftime('%Y-%m-%d'), next_d, equip_id]
            )
        return record_id

def list_maintenance_records(plan_id=None, equip_id=None, limit=50):
    with use_db() as db:
        sql = """
            SELECT mr.*, e.equip_name, e.equip_type
            FROM maintenance_record mr
            JOIN equipment e ON mr.equip_id=e.equip_id
            WHERE 1=1
        """
        params = []
        if plan_id:
            sql += " AND mr.plan_id=?"
            params.append(plan_id)
        if equip_id:
            sql += " AND mr.equip_id=?"
            params.append(equip_id)
        sql += " ORDER BY mr.record_time DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# 告警
# ─────────────────────────────────────────────

ALERT_THRESHOLDS = {
    'temp_high': 38.0,      # °C
    'temp_low':  30.0,
    'pH_high':   7.0,
    'pH_low':    4.0,
    'DO_low':    20.0,      # %
}

def check_and_alert(batch_id, equip_id, temp=None, pH=None, DO=None):
    """检查参数是否超阈值，超则写入告警"""
    alerts = []
    with use_db() as db:
        if temp is not None:
            if temp > ALERT_THRESHOLDS['temp_high']:
                _create_alert(db, batch_id, equip_id, 'temp_high', 'critical',
                              f"温度{temp}°C 超过上限{ALERT_THRESHOLDS['temp_high']}°C",
                              temp, ALERT_THRESHOLDS['temp_high'])
                alerts.append('temp_high')
            elif temp < ALERT_THRESHOLDS['temp_low']:
                _create_alert(db, batch_id, equip_id, 'temp_low', 'warning',
                              f"温度{temp}°C 低于下限{ALERT_THRESHOLDS['temp_low']}°C",
                              temp, ALERT_THRESHOLDS['temp_low'])
                alerts.append('temp_low')
        if pH is not None:
            if pH > ALERT_THRESHOLDS['pH_high']:
                _create_alert(db, batch_id, equip_id, 'pH_high', 'critical',
                              f"pH {pH} 超过上限{ALERT_THRESHOLDS['pH_high']}",
                              pH, ALERT_THRESHOLDS['pH_high'])
                alerts.append('pH_high')
            elif pH < ALERT_THRESHOLDS['pH_low']:
                _create_alert(db, batch_id, equip_id, 'pH_low', 'warning',
                              f"pH {pH} 低于下限{ALERT_THRESHOLDS['pH_low']}",
                              pH, ALERT_THRESHOLDS['pH_low'])
                alerts.append('pH_low')
        if DO is not None and DO < ALERT_THRESHOLDS['DO_low']:
            _create_alert(db, batch_id, equip_id, 'DO_low', 'critical',
                          f"溶解氧{DO}% 低于下限{ALERT_THRESHOLDS['DO_low']}%",
                          DO, ALERT_THRESHOLDS['DO_low'])
            alerts.append('DO_low')
    return alerts

def _create_alert(db, batch_id, equip_id, alert_type, level, message, value, threshold):
    db.execute("""
        INSERT INTO alerts (batch_id, equip_id, alert_type, level, message, value, threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [batch_id, equip_id, alert_type, level, message, value, threshold])

def list_alerts(status='active', limit=50):
    with use_db() as db:
        rows = db.execute(
            "SELECT * FROM alerts WHERE status=? ORDER BY created_at DESC LIMIT ?",
            [status, limit]
        ).fetchall()
        return [dict(r) for r in rows]

def resolve_alert(alert_id):
    with use_db() as db:
        db.execute(
            "UPDATE alerts SET status='resolved', resolved_at=datetime('now') WHERE alert_id=?",
            [alert_id]
        )

# ─────────────────────────────────────────────
# 班次管理
# ─────────────────────────────────────────────

SHIFT_TYPES = {
    'early': {'name': '早班', 'start': '08:00', 'end': '16:00'},
    'mid':   {'name': '中班', 'start': '16:00', 'end': '24:00'},
    'night': {'name': '夜班', 'start': '00:00', 'end': '08:00'},
}

def _make_shift_id():
    return f"SHIFT-{datetime.now().strftime('%Y%m%d')}-{_seq('SHIFT')}"

def create_shift(shift_date, shift_type, leader=None, start_time=None, end_time=None, status='active'):
    """创建班次记录"""
    shift_id = _make_shift_id()
    if shift_type in SHIFT_TYPES and start_time is None:
        start_time = f"{shift_date} {SHIFT_TYPES[shift_type]['start']}:00"
    if shift_type in SHIFT_TYPES and end_time is None:
        end_time = f"{shift_date} {SHIFT_TYPES[shift_type]['end']}:00"
    with use_db() as db:
        db.execute("""
            INSERT INTO shifts (shift_id, shift_date, shift_type, leader, start_time, end_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [shift_id, shift_date, shift_type, leader, start_time, end_time, status])
    return shift_id

def get_shift(shift_id):
    with use_db() as db:
        row = db.execute("SELECT * FROM shifts WHERE shift_id=?", [shift_id]).fetchone()
        return dict(row) if row else None

def get_current_shift():
    """根据当前时间返回活跃班次（自动匹配早/中/夜班）"""
    now = datetime.now()
    current_hour = now.hour
    # 早班: 8-16, 中班: 16-24(次日), 夜班: 0-8
    if 8 <= current_hour < 16:
        shift_type = 'early'
    elif 16 <= current_hour < 24:
        shift_type = 'mid'
    else:
        shift_type = 'night'
    shift_date = now.strftime('%Y-%m-%d')
    with use_db() as db:
        # 查找今天该班次类型的active班次
        row = db.execute("""
            SELECT * FROM shifts
            WHERE shift_date=? AND shift_type=? AND status='active'
            ORDER BY created_at DESC LIMIT 1
        """, [shift_date, shift_type]).fetchone()
        if row:
            return dict(row)
        # 如果没有active班次，创建一个新的
        shift_id = create_shift(shift_date, shift_type)
        row = db.execute("SELECT * FROM shifts WHERE shift_id=?", [shift_id]).fetchone()
        return dict(row) if row else None

def list_shifts(shift_date=None, status=None, limit=50):
    with use_db() as db:
        sql = "SELECT * FROM shifts WHERE 1=1"
        params = []
        if shift_date:
            sql += " AND shift_date=?"
            params.append(shift_date)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY shift_date DESC, shift_type, created_at DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def update_shift_status(shift_id, status):
    with use_db() as db:
        db.execute("UPDATE shifts SET status=? WHERE shift_id=?", [status, shift_id])
        row = db.execute("SELECT * FROM shifts WHERE shift_id=?", [shift_id]).fetchone()
        return dict(row) if row else None

# ─────────────────────────────────────────────
# 交接班记录
# ─────────────────────────────────────────────

HANDOVER_TYPE_LABELS = {
    'pre_shift': '班前交接',
    'mid_shift': '班中交接',
    'shift_end': '交班',
    'post_shift': '班后交接',
}

def create_handover(shift_id_out, shift_id_in=None, handover_type='shift_end',
                     content=None, issues=None, attachments=None, created_by=None):
    """创建交接记录"""
    if issues and not isinstance(issues, str):
        issues = json.dumps(issues, ensure_ascii=False)
    if attachments and not isinstance(attachments, str):
        attachments = json.dumps(attachments, ensure_ascii=False)
    with use_db() as db:
        cursor = db.execute("""
            INSERT INTO handover_records
            (shift_id_out, shift_id_in, handover_type, content, issues, attachments, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [shift_id_out, shift_id_in, handover_type, content, issues, attachments, created_by])
        record_id = cursor.lastrowid
    return record_id

def get_handover(record_id):
    with use_db() as db:
        row = db.execute("SELECT * FROM handover_records WHERE record_id=?", [record_id]).fetchone()
        return dict(row) if row else None

def confirm_handover(record_id, confirmed_by):
    """接班人确认交接"""
    with use_db() as db:
        db.execute("""
            UPDATE handover_records
            SET status='confirmed', confirmed_by=?, confirmed_at=datetime('now')
            WHERE record_id=?
        """, [confirmed_by, record_id])
        row = db.execute("SELECT * FROM handover_records WHERE record_id=?", [record_id]).fetchone()
        return dict(row) if row else None

def get_handover_history(limit=10):
    """获取最近交接记录列表"""
    with use_db() as db:
        rows = db.execute("""
            SELECT hr.*,
                   so.shift_type as shift_out_type, so.leader as leader_out,
                   si.shift_type as shift_in_type, si.leader as leader_in
            FROM handover_records hr
            LEFT JOIN shifts so ON hr.shift_id_out = so.shift_id
            LEFT JOIN shifts si ON hr.shift_id_in = si.shift_id
            ORDER BY hr.handover_time DESC
            LIMIT ?
        """, [limit]).fetchall()
        return [dict(r) for r in rows]

def cancel_handover(record_id):
    with use_db() as db:
        db.execute("UPDATE handover_records SET status='cancelled' WHERE record_id=?", [record_id])

# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

_counter_cache = {}
_seq_lock = threading.Lock()

def _seq(prefix):
    """带并发保护的序号生成，查询 DB 真实最大值"""
    today = datetime.now().strftime('%Y%m%d')
    key = f"{prefix}:{today}"
    # 用独立连接，避免与外层 use_db() 嵌套冲突
    db = get_db()
    with _seq_lock:
        try:
            pattern = f"{prefix}-{today}-%"
            row = db.execute(
                f"SELECT order_id FROM production_orders WHERE order_id LIKE ? ORDER BY order_id DESC LIMIT 1",
                (pattern,)
            ).fetchone()
            if not row:
                for tbl, col in [("batches", "batch_id"), ("quality_tests", "test_id"),
                                  ("alerts", "alert_id"), ("work_reports", "work_report_id")]:
                    row = db.execute(
                        f"SELECT {col} FROM {tbl} WHERE {col} LIKE ? ORDER BY {col} DESC LIMIT 1",
                        (f"{prefix}-{today}-%",)
                    ).fetchone()
                    if row:
                        break
            if row:
                last = int(dict(row)[list(dict(row).keys())[0]].split('-')[-1])
                cnt = last + 1
            else:
                cnt = _counter_cache.get(key, 0) + 1
            _counter_cache[key] = cnt
            return f"{cnt:03d}"
        finally:
            db.close()

def seed_demo_data():
    """写入演示数据"""
    init_db()
    with use_db() as db:
        existing = db.execute("SELECT COUNT(*) FROM production_orders").fetchone()[0]
        if existing > 0:
            print(f"[MES] 已存在 {existing} 条工单，跳过演示数据")
            return

        # 默认管理员账号（密码: mes2026）
        # 每次初始化时重新生成（bcrypt salt 不同是正常行为）
        import bcrypt as _bcrypt
        admin_hash = _bcrypt.hashpw("mes2026".encode(), _bcrypt.gensalt()).decode()
        try:
            db.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, full_name, role, department) "
                "VALUES (?, ?, ?, ?, ?)",
                ("admin", admin_hash, "系统管理员", "admin", "信息中心")
            )
        except Exception as e:
            print(f"[MES] admin用户创建: {e}")

    # 设备
    for eq in [
        ("FER-01", "1号发酵罐", "fermenter", "CCT-5000L", "发酵车间A区"),
        ("FER-02", "2号发酵罐", "fermenter", "CCT-5000L", "发酵车间A区"),
        ("FER-03", "3号发酵罐", "fermenter", "CCT-3000L", "发酵车间B区"),
        ("CENT-01", "1号离心机", "centrifuge", "NX-450", "分离车间"),
        ("DRY-01", "沸腾干燥床", "dryer", "FG-120", "干燥车间"),
        ("STER-01", "灭菌锅", "sterilizer", "HV-2000", "预处理车间"),
    ]:
        create_equipment(*eq)

    # 工单
    order1 = create_order("ENZYME-001", "中性蛋白酶", 5000, "FER-01",
                          plan_start="2026-05-02 08:00", plan_end="2026-05-05 08:00")
    order2 = create_order("ENZYME-002", "糖化酶", 3000, "FER-02",
                          plan_start="2026-05-02 10:00", plan_end="2026-05-04 10:00")
    order3 = create_order("ENZYME-003", "脂肪酶", 2000, "FER-03",
                          plan_start="2026-05-03 08:00", plan_end="2026-05-06 08:00", priority=1)

    # 批次
    batch1 = create_batch(order1)
    batch2 = create_batch(order2)
    with use_db() as db:
        db.execute("UPDATE batches SET stage='fermentation', stage_index=3, start_time=datetime('now', '-4 hours') WHERE batch_id=?", [batch1])
        db.execute("UPDATE batches SET stage='seed', stage_index=2 WHERE batch_id=?", [batch2])
        db.execute("UPDATE production_orders SET status='in_progress' WHERE order_id=?", [order1])

    # 模拟工艺参数
    for i in range(10):
        record_batch_params(batch1,
                           temp=36.0 + (i % 3) * 0.5,
                           pH=6.2 + (i % 2) * 0.1,
                           DO=85 - i * 2,
                           stir_speed=150 + i * 5)

    # 质检
    create_quality_test(batch1, 'in_process', '李检验',
                         enzyme_activity=2450, moisture=5.2,
                         microbial_count=300, pH_value=6.3, appearance='淡黄色粉末')
    # 默认质量标准
    seed_default_quality_specs()
    print("[MES] 演示数据写入完成")


if __name__ == "__main__":
    seed_demo_data()
    print("[MES] 模块自测完成")
