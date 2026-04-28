#!/usr/bin/env python3
"""
xiaoV Factory — 时序数据库引擎
纯SQLite实现，支持：点写入、自动降采样、保留策略、查询聚合
类似InfluxDB/TDengine的核心概念，零外部依赖
"""
import sqlite3, time, json, os, threading
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'timeseries.db')

# 保留策略（秒）
RETENTION = {
    'raw': 7 * 24 * 3600,          # 原始数据: 7天
    '1m': 30 * 24 * 3600,          # 1分钟聚合: 30天
    '1h': 365 * 24 * 3600,         # 1小时聚合: 365天
}


class TimeSeriesDB:
    """时序数据库 — 支持tag+field+timestamp，自动降采样和保留策略"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.lock = threading.Lock()
        self._init_schema()
        self.write_count = 0

    def _init_schema(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # 指标元数据
        c.execute("""CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            unit TEXT,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        # 原始数据点
        c.execute("""CREATE TABLE IF NOT EXISTS data_points (
            ts INTEGER NOT NULL,          -- unix timestamp (毫秒)
            metric_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            value REAL NOT NULL,
            tags TEXT DEFAULT '{}',       -- JSON
            PRIMARY KEY (metric_id, device_id, ts)
        ) WITHOUT ROWID""")

        # 1分钟聚合
        c.execute("""CREATE TABLE IF NOT EXISTS agg_1m (
            ts_bucket INTEGER NOT NULL,   -- 对齐到分钟的时间戳(秒)
            metric_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            min_val REAL, max_val REAL, avg_val REAL, count_val INTEGER,
            PRIMARY KEY (metric_id, device_id, ts_bucket)
        ) WITHOUT ROWID""")

        # 1小时聚合
        c.execute("""CREATE TABLE IF NOT EXISTS agg_1h (
            ts_bucket INTEGER NOT NULL,
            metric_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            min_val REAL, max_val REAL, avg_val REAL, count_val INTEGER,
            PRIMARY KEY (metric_id, device_id, ts_bucket)
        ) WITHOUT ROWID""")

        # 降采样偏移量（记录最后一次降采样的位置）
        c.execute("""CREATE TABLE IF NOT EXISTS downsampling_offset (
            granularity TEXT PRIMARY KEY,
            last_ts INTEGER NOT NULL DEFAULT 0
        )""")

        conn.commit()
        conn.close()

    def register_metric(self, name, unit='', description=''):
        """注册指标"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("INSERT OR IGNORE INTO metrics (name, unit, description) VALUES (?,?,?)",
                        (name, unit, description))
            conn.commit()
            row = conn.execute("SELECT id FROM metrics WHERE name=?", (name,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def get_metric_id(self, name):
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT id FROM metrics WHERE name=?", (name,)).fetchone()
        conn.close()
        return row[0] if row else None

    def write(self, metric, device_id, value, tags=None, timestamp=None):
        """写入一个数据点"""
        ts = timestamp or int(time.time() * 1000)
        tags_json = json.dumps(tags or {}, ensure_ascii=False)

        conn = sqlite3.connect(self.db_path)
        mid = self.get_metric_id(metric)
        if mid is None:
            mid = self.register_metric(metric)

        try:
            conn.execute(
                "INSERT OR REPLACE INTO data_points (ts, metric_id, device_id, value, tags) VALUES (?,?,?,?,?)",
                (ts, mid, device_id, value, tags_json)
            )
            conn.commit()
            self.write_count += 1
        finally:
            conn.close()

    def write_batch(self, points):
        """批量写入 [(metric, device_id, value, tags, timestamp), ...]"""
        conn = sqlite3.connect(self.db_path)
        for metric, device_id, value, tags, timestamp in points:
            ts = timestamp or int(time.time() * 1000)
            mid = self.get_metric_id(metric)
            if mid is None:
                mid = self.register_metric(metric)
            conn.execute(
                "INSERT OR REPLACE INTO data_points (ts, metric_id, device_id, value, tags) VALUES (?,?,?,?,?)",
                (ts, mid, device_id, value, json.dumps(tags or {}))
            )
            self.write_count += 1
        conn.commit()
        conn.close()

    def query(self, metric, device_id=None, start_ts=None, end_ts=None, agg='raw', limit=1000):
        """查询时序数据"""
        mid = self.get_metric_id(metric)
        if mid is None:
            return []

        conn = sqlite3.connect(self.db_path)

        if agg == 'raw':
            table = 'data_points'
            sql = "SELECT ts, value, tags FROM data_points WHERE metric_id=? "
            params = [mid]
        elif agg == '1m':
            table = 'agg_1m'
            sql = "SELECT ts_bucket*1000, avg_val, min_val, max_val, count_val FROM agg_1m WHERE metric_id=? "
            params = [mid]
        elif agg == '1h':
            table = 'agg_1h'
            sql = "SELECT ts_bucket*1000, avg_val, min_val, max_val, count_val FROM agg_1h WHERE metric_id=? "
            params = [mid]
        else:
            return []

        if device_id:
            sql += f"AND device_id=? "
            params.append(device_id)
        if start_ts:
            if agg == 'raw':
                sql += f"AND ts>=? "
            else:
                sql += f"AND ts_bucket*1000>=? "
            params.append(start_ts)
        if end_ts:
            if agg == 'raw':
                sql += f"AND ts<=? "
            else:
                sql += f"AND ts_bucket*1000<=? "
            params.append(end_ts)

        if agg == 'raw':
            sql += "ORDER BY ts DESC LIMIT ?"
        else:
            sql += "ORDER BY ts_bucket DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        conn.close()

        results = []
        for row in rows:
            if agg == 'raw':
                results.append({"timestamp": row[0], "value": row[1], "tags": row[2]})
            else:
                results.append({"timestamp": row[0], "avg": row[1], "min": row[2], "max": row[3], "count": row[4]})
        return results

    def _get_data_range(self, conn):
        """获取数据的最小/最大时间戳"""
        row = conn.execute("SELECT MIN(ts), MAX(ts) FROM data_points").fetchone()
        if row and row[0] and row[1]:
            return row[0], row[1]
        return None, None

    def downsampling(self):
        """执行降采样：raw → 1m → 1h  (仅处理有数据的范围，避免从epoch迭代)"""
        conn = sqlite3.connect(self.db_path)
        now = int(time.time())
        min_ts, max_ts = self._get_data_range(conn)
        if min_ts is None or max_ts is None:
            conn.close()
            return

        # 获取上次降采样的偏移量
        offsets = {}
        for row in conn.execute("SELECT granularity, last_ts FROM downsampling_offset").fetchall():
            offsets[row[0]] = row[1]

        raw_offset = max(offsets.get('raw', 0), min_ts)
        agg1m_offset = offsets.get('1m', 0)

        # raw → 1m 聚合 — SQL GROUP BY 批量处理
        raw_since = max(raw_offset, min_ts)
        bucket_size = 60
        bucket_start = (raw_since // (bucket_size * 1000)) * bucket_size
        bucket_end = min(((max_ts // (bucket_size * 1000)) + 1) * bucket_size, (now // bucket_size) * bucket_size)

        if bucket_start >= bucket_end:
            conn.close()
            return

        conn.execute(f"""INSERT OR REPLACE INTO agg_1m (ts_bucket, metric_id, device_id, min_val, max_val, avg_val, count_val)
            SELECT (ts / {bucket_size * 1000}) * {bucket_size} AS bucket,
                   metric_id, device_id,
                   MIN(value), MAX(value), ROUND(AVG(value), 4), COUNT(*)
            FROM data_points
            WHERE ts >= ? AND ts < ?
            GROUP BY bucket, metric_id, device_id
        """, (bucket_start * 1000, bucket_end * 1000 + 60000))

        conn.execute("INSERT OR REPLACE INTO downsampling_offset (granularity, last_ts) VALUES ('raw', ?)",
                    (bucket_end * 1000,))

        # 1m → 1h 聚合 — SQL GROUP BY 批量处理
        min_1m, max_1m = conn.execute("SELECT MIN(ts_bucket), MAX(ts_bucket) FROM agg_1m").fetchone() or (None, None)
        if min_1m is None or max_1m is None:
            conn.commit()
            conn.close()
            return

        hour_since = max(agg1m_offset if agg1m_offset > 0 else raw_offset, min_1m * 1000)
        hour_start = (hour_since // 3600000) * 3600
        hour_end = ((max_1m // 3600) + 1) * 3600

        conn.execute(f"""INSERT OR REPLACE INTO agg_1h (ts_bucket, metric_id, device_id, min_val, max_val, avg_val, count_val)
            SELECT (ts_bucket / 3600) * 3600 AS bucket,
                   metric_id, device_id,
                   MIN(min_val), MAX(max_val), ROUND(AVG(avg_val), 4), SUM(count_val)
            FROM agg_1m
            WHERE ts_bucket >= ? AND ts_bucket < ?
            GROUP BY bucket, metric_id, device_id
        """, (hour_start, hour_end))

        conn.execute("INSERT OR REPLACE INTO downsampling_offset (granularity, last_ts) VALUES ('1m', ?)",
                    (hour_end,))
        conn.commit()
        conn.close()

    def purge_old_data(self):
        """清理过期数据"""
        now = int(time.time() * 1000)
        cutoff_raw = now - RETENTION['raw'] * 1000
        cutoff_1m = now - RETENTION['1m'] * 1000
        cutoff_1h = now - RETENTION['1h'] * 1000

        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM data_points WHERE ts < ?", (cutoff_raw,))
        conn.execute("DELETE FROM agg_1m WHERE ts_bucket * 1000 < ?", (cutoff_1m,))
        conn.execute("DELETE FROM agg_1h WHERE ts_bucket * 1000 < ?", (cutoff_1h,))
        conn.commit()
        conn.close()

    def backfill(self, metric, device_id, values, start_ts, interval_ms=1000):
        """数据补传 — 批量补录历史数据"""
        points = []
        ts = start_ts
        for v in values:
            points.append((metric, device_id, v, {}, ts))
            ts += interval_ms
        self.write_batch(points)
        return len(points)

    def stats(self):
        conn = sqlite3.connect(self.db_path)
        raw = conn.execute("SELECT COUNT(*) FROM data_points").fetchone()[0]
        agg1m = conn.execute("SELECT COUNT(*) FROM agg_1m").fetchone()[0]
        agg1h = conn.execute("SELECT COUNT(*) FROM agg_1h").fetchone()[0]
        metrics = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        conn.close()
        return {"metrics": metrics, "raw_points": raw, "agg_1m": agg1m, "agg_1h": agg1h, "total_writes": self.write_count}


# 示例
if __name__ == '__main__':
    import random
    db = TimeSeriesDB()
    print("=" * 50)
    print("  xiaoV Factory · 时序数据库引擎")
    print("=" * 50)

    # 注册指标
    for name, unit in [("temperature", "℃"), ("ph", ""), ("pressure", "MPa"), ("dissolved_oxygen", "%")]:
        db.register_metric(name, unit, f"{name} sensor data")
    print(f"  注册 4 个指标")

    # 写入数据 — 模拟3台设备、10分钟数据
    devices = [f"fermenter-{i:02d}" for i in range(3)]
    now = int(time.time() * 1000)

    print(f"  写入模拟数据...")
    for i in range(600):  # 600个时间点 / 10分钟
        for dev in devices:
            t = now - (600 - i) * 1000
            db.write("temperature", dev, 36 + random.gauss(0, 0.5), {"unit": "℃"}, t)
            db.write("ph", dev, 6.8 + random.gauss(0, 0.05), {"unit": ""}, t)
            db.write("pressure", dev, 0.08 + random.gauss(0, 0.01), {"unit": "MPa"}, t)
            if i % 3 == 0:  # 每3秒记录一次溶氧
                db.write("dissolved_oxygen", dev, 85 + random.gauss(0, 3), {"unit": "%"}, t)
        if i % 100 == 0:
            print(f"    {i}/600 数据点写入...")

    print(f"\n  执行降采样...")
    db.downsampling()

    print(f"\n  统计: {json.dumps(db.stats(), indent=2)}")

    # 查询最近温度数据
    print(f"\n  查询温度数据(最后5条)...")
    results = db.query("temperature", "fermenter-00", agg='raw', limit=5)
    for r in results[:3]:
        print(f"    ts={r['timestamp']}, value={r['value']:.2f}")

    # 查询1分钟聚合
    print(f"\n  查询1分钟聚合...")
    agg_results = db.query("temperature", "fermenter-00", agg='1m', limit=3)
    for r in agg_results:
        print(f"    bucket={r['timestamp']}, avg={r['avg']:.2f}, min={r['min']:.2f}, max={r['max']:.2f}, count={r['count']}")

    # 测试数据补传
    print(f"\n  测试数据补传(backfill)...")
    start_ts = now - 24 * 3600 * 1000  # 24小时前
    backfill_values = [36.0 + i * 0.1 for i in range(100)]
    n = db.backfill("temperature", "fermenter-00", backfill_values, start_ts, 60000)  # 每分钟一个点
    print(f"    补传 {n} 个数据点")
    print(f"  统计: {json.dumps(db.stats(), indent=2)}")
