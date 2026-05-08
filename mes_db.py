"""
MES 数据库抽象层
支持 SQLite（开发/轻量）和 PostgreSQL（生产/多用户）

切换方式：环境变量 DATABASE_URL
  未设置 / sqlite:///mes.db  → SQLite
  postgresql://...            → PostgreSQL

PostgreSQL 初始化：psql < postgres/init.sql
"""

import os
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, date, time
from urllib.parse import urlparse

# ─── 连接配置 ───────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgresql://")

if USE_PG:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_PATH = DATABASE_URL  # postgresql://user:pass@host:5432/mes
else:
    DB_PATH = os.environ.get("MES_DB_PATH", "/Users/xuyan/software/hermesWorkspace/mes.db")


# ─── PostgreSQL 连接 ─────────────────────────────────────

def get_pg_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# ─── SQLite 连接 ────────────────────────────────────────

def get_sqlite_connection():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


# ─── 统一接口 ───────────────────────────────────────────

def get_db():
    """统一入口，返回标准 DB-API 2.0 cursor"""
    if USE_PG:
        return get_pg_connection()
    return get_sqlite_connection()


@contextmanager
def use_db():
    """上下文管理器，自动 commit"""
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─── SQL 兼容层（SQLite ← → PostgreSQL）───────────────

def _pg(conn):
    """返回 PostgreSQL dict cursor，或 SQLite dict wrapper"""
    if USE_PG:
        return conn
    # SQLite: 把 Row 转为 dict
    class DictRow:
        def __init__(self, row):
            self._row = row
        def __getitem__(self, key):
            try:
                return self._row[key]
            except TypeError:
                return getattr(self._row, key)
        def keys(self):
            return self._row.keys()
        def get(self, key, default=None):
            try:
                return self._row[key]
            except (TypeError, KeyError):
                return default
    return DictRow


def dict_from_row(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


# ─── 类型序列化 ─────────────────────────────────────────

def _json_dumps(obj):
    if obj is None:
        return None
    if isinstance(obj, (dict, list)):
        return json.dumps(obj, ensure_ascii=False, default=str)
    return obj


def _json_loads(val):
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val
    return val


# ─── 时间戳兼容 ─────────────────────────────────────────

def _now():
    return datetime.now().isoformat()


def _date_str(dt):
    """统一返回 ISO 日期字符串，兼容 SQLite/PG"""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt[:10]
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()[:10]
    return str(dt)


# ─── 迁移脚本（SQLite → PostgreSQL）───────────────────

def export_sqlite_to_sql():
    """读取 mes.db，输出可执行的 PostgreSQL INSERT 语句"""
    import sqlite3 as sq
    conn = sq.connect("/Users/xuyan/software/hermesWorkspace/mes.db")
    conn.row_factory = sq.Row
    cur = conn.cursor()

    tables = [
        "users", "production_orders", "batches", "batch_params",
        "quality_tests", "quality_specs", "equipment",
        "maintenance_plan", "maintenance_record",
        "alerts", "work_reports", "shifts", "handover_records"
    ]

    output = []
    for tbl in tables:
        cur.execute(f"SELECT * FROM {tbl}")
        cols = [d[0] for d in cur.description]
        for row in cur.fetchall():
            vals = []
            for v in row:
                if v is None:
                    vals.append("NULL")
                elif isinstance(v, str):
                    vals.append(f"E'{v.replace("'", "''")}'")
                else:
                    vals.append(str(v))
            sql = f"INSERT INTO {tbl} ({', '.join(cols)}) VALUES ({', '.join(vals)});"
            output.append(sql)

    conn.close()
    return "\n".join(output)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "export":
        print(export_sqlite_to_sql())
