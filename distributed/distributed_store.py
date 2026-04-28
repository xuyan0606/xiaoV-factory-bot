#!/usr/bin/env python3
"""
xiaoV Industrial IoT — 分布式数据存储
分片存储、主从复制、故障检测、数据补传
"""
import asyncio, json, time, logging, sqlite3, os, threading
from datetime import datetime
from hashlib import md5

logging.basicConfig(level=logging.INFO, format='[DSTORE] %(message)s')
log = logging.getLogger('DSTORE')

class Shard:
    """单个数据分片"""
    def __init__(self, shard_id, db_path):
        self.shard_id = shard_id
        self.db_path = db_path
        self.data = {}    # msg_id -> payload (内存缓存)
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id TEXT UNIQUE, device_id TEXT, payload TEXT,
            created_at TEXT, stored_at TEXT)""")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_device ON sensor_data(device_id)""")
        conn.commit()
        conn.close()

    def write(self, msg_id, device_id, payload):
        with self.lock:
            self.data[msg_id] = payload
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("INSERT INTO sensor_data (msg_id, device_id, payload, created_at, stored_at) VALUES (?,?,?,?,?)",
                            (msg_id, device_id, json.dumps(payload), payload.get('timestamp', datetime.now().isoformat()), datetime.now().isoformat()))
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # 重复写
            finally:
                conn.close()

    def read(self, device_id, limit=100):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT payload FROM sensor_data WHERE device_id=? ORDER BY id DESC LIMIT ?",
                           (device_id, limit)).fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    def count(self):
        conn = sqlite3.connect(self.db_path)
        n = conn.execute("SELECT COUNT(*) FROM sensor_data").fetchone()[0]
        conn.close()
        return n

    def last_30s_count(self):
        cutoff = (datetime.now().timestamp() - 30) * 1000
        conn = sqlite3.connect(self.db_path)
        n = conn.execute("SELECT COUNT(*) FROM sensor_data WHERE id > ?",
                        (int(cutoff),)).fetchone()[0]
        conn.close()
        return n


class ShardManager:
    """分片管理器 — 按设备ID哈希分片"""
    def __init__(self, shard_count=4, base_dir='/tmp/shard_db'):
        self.shard_count = shard_count
        self.base_dir = base_dir
        self.shards = {}
        os.makedirs(base_dir, exist_ok=True)
        for i in range(shard_count):
            path = os.path.join(base_dir, f'shard_{i}.db')
            self.shards[i] = Shard(i, path)

    def _shard_id(self, device_id):
        return int(md5(device_id.encode()).hexdigest(), 16) % self.shard_count

    def write(self, msg_id, device_id, payload):
        sid = self._shard_id(device_id)
        self.shards[sid].write(msg_id, device_id, payload)

    def read(self, device_id, limit=100):
        sid = self._shard_id(device_id)
        return self.shards[sid].read(device_id, limit)

    def stats(self):
        return {f"shard_{i}": {"count": s.count(), "last_30s": s.last_30s_count()}
                for i, s in self.shards.items()}


class ReplicaSet:
    """主从复制组"""
    def __init__(self, name, master_shard, slave_shards=None, sync_interval=1):
        self.name = name
        self.master = master_shard   # Shard实例
        self.slaves = slave_shards or []
        self.sync_interval = sync_interval
        self.replication_lag = 0
        self.last_sync_id = 0
        self.running = False

    async def start_replication(self):
        """启动异步复制"""
        self.running = True
        asyncio.create_task(self._sync_loop())

    async def _sync_loop(self):
        while self.running:
            try:
                start = time.time()
                # 模拟从主库读取增量数据并同步到从库
                conn = sqlite3.connect(self.master.db_path)
                rows = conn.execute(
                    "SELECT msg_id, device_id, payload, created_at FROM sensor_data WHERE id > ? ORDER BY id",
                    (self.last_sync_id,)).fetchall()
                conn.close()

                if rows:
                    for slave in self.slaves:
                        sconn = sqlite3.connect(slave.db_path)
                        for row in rows:
                            try:
                                sconn.execute("INSERT INTO sensor_data (msg_id, device_id, payload, created_at, stored_at) VALUES (?,?,?,?,?)",
                                            (row[0], row[1], row[2], row[3], datetime.now().isoformat()))
                            except sqlite3.IntegrityError:
                                pass
                        sconn.commit()
                        sconn.close()
                    self.last_sync_id = rows[-1][0]

                self.replication_lag = int((time.time() - start) * 1000)
                if rows:
                    log.info(f"[{self.name}] 同步 {len(rows)} 条, 延迟 {self.replication_lag}ms")
            except Exception as e:
                log.error(f"[{self.name}] 同步失败: {e}")
            await asyncio.sleep(self.sync_interval)

    def promote_slave(self, slave_idx=0):
        """从库提升为主库（故障切换）"""
        if slave_idx < len(self.slaves):
            log.warning(f"[{self.name}] 提升从库 {slave_idx} 为主库")
            self.master = self.slaves.pop(slave_idx)
            return True
        return False

    def stop(self):
        self.running = False


class DistributedStore:
    """分布式存储系统"""
    def __init__(self, shard_count=4, replica_factor=2):
        self.sm = ShardManager(shard_count)
        self.replica_factor = min(replica_factor, shard_count)
        self.replica_sets = {}
        self.total_writes = 0
        self.total_reads = 0

    def write(self, msg_id, device_id, payload):
        # 主分片写入
        self.sm.write(msg_id, device_id, payload)
        self.total_writes += 1

        # 副本写入（同分片多个副本
        for i in range(1, self.replica_factor):
            replica_sid = (self.sm._shard_id(device_id) + i) % self.sm.shard_count
            self.sm.shards[replica_sid].write(f"{msg_id}_r{i}", device_id, payload)

    def read(self, device_id, limit=100):
        self.total_reads += 1
        return self.sm.read(device_id, limit)

    def stats(self):
        return {
            "shards": self.sm.stats(),
            "total_writes": self.total_writes,
            "total_reads": self.total_reads,
            "replica_factor": self.replica_factor
        }


# 示例
async def demo():
    store = DistributedStore(shard_count=4, replica_factor=2)

    # 写入传感器数据
    devices = [f"fermenter-{i:02d}" for i in range(5)]
    for ts in range(10):
        for dev in devices:
            msg_id = f"{dev}_{ts}"
            payload = {"device_id": dev, "temperature": 35 + ts * 0.5, "ph": 6.5 + ts * 0.05, "timestamp": datetime.now().isoformat()}
            store.write(msg_id, dev, payload)
        await asyncio.sleep(0.1)

    log.info(f"存储统计: {store.stats()}")
    log.info(f"发酵罐-00 最近数据: {len(store.read('fermenter-00'))}条")

if __name__ == '__main__':
    asyncio.run(demo())
