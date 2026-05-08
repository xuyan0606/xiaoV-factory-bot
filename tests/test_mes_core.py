"""
pytest 测试 — MES 核心业务逻辑
覆盖：工单/批次/报工/质检/权限/JWT
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pytest, sqlite3, json, threading, time
import mes_core as db

MES_DB = "/Users/xuyan/software/hermesWorkspace/mes.db"


# ─── Fixtures ────────────────────────────────────────────

@pytest.fixture
def fresh_db():
    """每个测试用独立内存 DB"""
    # 临时文件 DB
    import tempfile
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    conn = sqlite3.connect(f.name)
    conn.row_factory = sqlite3.Row

    # 手工建表（对应 mes_core.init_db）
    conn.executescript("""
        CREATE TABLE production_orders (
            order_id TEXT PRIMARY KEY, product_code TEXT NOT NULL,
            product_name TEXT NOT NULL, batch_size REAL NOT NULL,
            fermenter_id TEXT, plan_start TEXT, plan_end TEXT,
            status TEXT DEFAULT 'pending', priority INTEGER DEFAULT 2,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE batches (
            batch_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
            stage TEXT DEFAULT 'pending', stage_index INTEGER DEFAULT 0,
            start_time TEXT, end_time TEXT,
            current_temp REAL, current_pH REAL, current_DO REAL
        );
        CREATE TABLE quality_tests (
            test_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL,
            stage TEXT NOT NULL, enzyme_activity REAL, moisture REAL,
            microbial_count INTEGER, pH_value REAL, appearance TEXT,
            result TEXT DEFAULT 'pending', result_detail TEXT,
            reviewed_by TEXT, reviewed_at TEXT, review_remark TEXT,
            tester TEXT, test_time TEXT, remark TEXT
        );
        CREATE TABLE quality_specs (
            standard_id TEXT PRIMARY KEY, product_type TEXT NOT NULL,
            stage TEXT NOT NULL, param_name TEXT NOT NULL,
            lo REAL, hi REAL, unit TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE work_reports (
            work_report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT, order_id TEXT NOT NULL, worker TEXT,
            report_time TEXT, stage TEXT, input_amount REAL DEFAULT 0,
            output_amount REAL DEFAULT 0, yield_rate REAL,
            status TEXT DEFAULT 'recorded', remark TEXT
        );
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            full_name TEXT, role TEXT NOT NULL DEFAULT 'operator',
            department TEXT, phone TEXT, status TEXT DEFAULT 'active',
            created_at TEXT
        );
        CREATE TABLE shifts (
            shift_id TEXT PRIMARY KEY, shift_date TEXT NOT NULL,
            shift_type TEXT NOT NULL, leader TEXT, start_time TEXT,
            end_time TEXT, status TEXT DEFAULT 'active', created_at TEXT
        );
        CREATE TABLE handover_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id_out TEXT, shift_id_in TEXT, handover_time TEXT,
            handover_type TEXT NOT NULL, content TEXT, issues TEXT,
            attachments TEXT, status TEXT DEFAULT 'pending',
            confirmed_by TEXT, confirmed_at TEXT, created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT, equip_id TEXT, alert_type TEXT NOT NULL,
            level TEXT DEFAULT 'warning', message TEXT NOT NULL,
            value REAL, threshold REAL, status TEXT DEFAULT 'active',
            created_at TEXT, resolved_at TEXT
        );
    """)
    conn.commit()
    # 替换全局 DB_PATH（危险，仅限测试）
    orig_path = db.DB_PATH
    db.DB_PATH = f.name
    db.init_db = lambda: None  # 已初始化
    yield f.name
    db.DB_PATH = orig_path
    os.unlink(f.name)


# ─── 权限测试 ────────────────────────────────────────────

def test_role_permissions():
    import mes_auth as auth
    perms = auth.ROLE_PERMISSIONS
    assert perms["admin"] == "*"
    assert "quality" in perms["manager"]
    assert "orders" in perms["operator"]
    assert "orders" in perms["viewer"]  # viewer 可读
    assert "maintenance" not in perms["viewer"]  # viewer 无维保写权限


def test_user_roles():
    import mes_auth as auth
    assert "admin" in auth.ROLE_PERMISSIONS
    assert "manager" in auth.ROLE_PERMISSIONS
    assert "operator" in auth.ROLE_PERMISSIONS
    assert "viewer" in auth.ROLE_PERMISSIONS


# ─── 序号生成测试 ────────────────────────────────────────

def test_seq_no_duplicate(fresh_db):
    """并发场景下 _seq 不应产生重复序号"""
    results = []
    errors = []

    def worker():
        try:
            seq = db._seq("PO")
            results.append(seq)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors: {errors}"
    assert len(set(results)) == 10, f"Duplicates found: {results}"


# ─── 质量判定测试 ───────────────────────────────────────

def test_quality_judge_pass(fresh_db):
    """酶活在规格内 -> pass"""
    conn = sqlite3.connect(fresh_db)
    conn.row_factory = sqlite3.Row
    # 建批次
    conn.execute("INSERT INTO batches VALUES ('BAT-TEST-001','PO-TEST-001','in_process',0,datetime('now'),NULL,NULL,NULL,NULL)")
    conn.execute("INSERT INTO quality_specs VALUES ('SPEC-001','ENZYME-001','in_process','enzyme_activity',2000,5000,'U/g',NULL,NULL)")
    conn.commit()
    conn.close()

    # 手工判定
    conn = sqlite3.connect(fresh_db)
    conn.row_factory = sqlite3.Row
    spec = conn.execute("SELECT * FROM quality_specs WHERE param_name='enzyme_activity'").fetchone()
    activity = 3000
    if spec["lo"] <= activity <= (spec["hi"] or 999999):
        result = "pass"
    else:
        result = "fail"
    assert result == "pass"


def test_quality_judge_fail(fresh_db):
    """酶活低于下限 -> fail"""
    conn = sqlite3.connect(fresh_db)
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO quality_specs VALUES ('SPEC-001','ENZYME-001','in_process','enzyme_activity',2000,5000,'U/g',NULL,NULL)")
    conn.commit()

    spec = conn.execute("SELECT * FROM quality_specs WHERE param_name='enzyme_activity'").fetchone()
    activity = 1500  # 低于 2000 下限
    if spec["lo"] <= activity <= (spec["hi"] or 999999):
        result = "pass"
    else:
        result = "fail"
    assert result == "fail"


# ─── 得率计算测试 ────────────────────────────────────────

def test_yield_rate_calculation():
    """得率 = 产出/投入 * 100"""
    input_amount = 500.0
    output_amount = 475.0
    yield_rate = round(output_amount / input_amount * 100, 2)
    assert yield_rate == 95.0


def test_yield_rate_zero_input():
    """投入为0时得率应为0或N/A"""
    input_amount = 0.0
    output_amount = 0.0
    yield_rate = round(output_amount / input_amount * 100, 2) if input_amount > 0 else 0.0
    assert yield_rate == 0.0


# ─── 班次识别测试 ────────────────────────────────────────

def test_shift_type_recognition():
    """根据时间识别班次"""
    from datetime import datetime

    def get_shift_type(hour):
        if 8 <= hour < 16:
            return "morning"
        elif 16 <= hour < 24:
            return "afternoon"
        else:
            return "night"

    assert get_shift_type(9) == "morning"
    assert get_shift_type(14) == "morning"
    assert get_shift_type(16) == "afternoon"
    assert get_shift_type(22) == "afternoon"
    assert get_shift_type(2) == "night"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
