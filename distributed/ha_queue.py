#!/usr/bin/env python3
"""
xiaoV Industrial IoT — 高可用消息队列
支持持久化、ACK确认、死信队列、背压控制
"""
import asyncio, json, time, logging, os, sqlite3
from collections import deque
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='[HAQ] %(message)s')
log = logging.getLogger('HAQ')

class HAQueue:
    """高可用消息队列 — 支持持久化和ACK确认"""
    def __init__(self, name, db_path=None, max_queue=10000):
        self.name = name
        self.max_queue = max_queue
        self.memory_queue = deque()
        self.processing = {}  # msg_id -> (msg, timestamp)
        self.dlq = deque(maxlen=1000)  # 死信队列
        self.msg_counter = 0
        self.backpressure = False

        # SQLite持久化
        self.db_path = db_path or f'/tmp/haq_{name}.db'
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            msg_id TEXT UNIQUE, payload TEXT, created_at TEXT,
            status TEXT DEFAULT 'pending')""")
        c.execute("""CREATE TABLE IF NOT EXISTS dlq (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id TEXT, payload TEXT, error TEXT, created_at TEXT)""")
        conn.commit()
        conn.close()

    async def put(self, payload, msg_id=None):
        """生产消息"""
        if len(self.memory_queue) >= self.max_queue:
            self.backpressure = True
            raise Exception(f"队列[{self.name}]满, 背压触发")

        self.msg_counter += 1
        msg_id = msg_id or f"{self.name}_{self.msg_counter}_{int(time.time()*1000000)}"
        msg = {"id": msg_id, "payload": payload, "created_at": datetime.now().isoformat()}

        self.memory_queue.append(msg)
        self._persist(msg_id, json.dumps(payload))
        self.backpressure = len(self.memory_queue) > self.max_queue * 0.8
        return msg_id

    async def get(self, timeout=5):
        """消费消息（非阻塞+超时）"""
        start = time.time()
        while time.time() - start < timeout:
            if self.memory_queue:
                msg = self.memory_queue.popleft()
                self.processing[msg["id"]] = (msg, time.time())
                return msg
            await asyncio.sleep(0.1)
        return None

    async def ack(self, msg_id):
        """确认消息处理成功"""
        if msg_id in self.processing:
            del self.processing[msg_id]
            self._update_status(msg_id, 'completed')

    async def nack(self, msg_id, error="", requeue=True):
        """拒绝消息，可选择重新入队或进死信"""
        if msg_id in self.processing:
            msg, _ = self.processing.pop(msg_id)
            if requeue:
                self.memory_queue.appendleft(msg)  # 重新入队
                log.warning(f"[{self.name}] 重新入队: {msg_id}")
            else:
                self.dlq.append(msg)
                self._persist_dlq(msg_id, json.dumps(msg["payload"]), error)
                log.warning(f"[{self.name}] 死信: {msg_id} - {error}")

    def _persist(self, msg_id, payload):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("INSERT INTO messages (msg_id, payload, created_at) VALUES (?,?,?)",
                        (msg_id, payload, datetime.now().isoformat()))
            conn.commit()
        except: pass
        finally: conn.close()

    def _update_status(self, msg_id, status):
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE messages SET status=? WHERE msg_id=?", (status, msg_id))
        conn.commit()
        conn.close()

    def _persist_dlq(self, msg_id, payload, error):
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO dlq (msg_id, payload, error, created_at) VALUES (?,?,?,?)",
                    (msg_id, payload, error, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    @property
    def size(self):
        return len(self.memory_queue)

    @property
    def stats(self):
        return {
            "name": self.name,
            "memory_queue": len(self.memory_queue),
            "processing": len(self.processing),
            "dlq": len(self.dlq),
            "backpressure": self.backpressure,
            "max_queue": self.max_queue
        }


class ConsumerGroup:
    """消费者组 — 多个消费者竞争消费"""
    def __init__(self, queue, group_name, workers=3):
        self.queue = queue
        self.group_name = group_name
        self.workers = workers
        self.running = False

    async def start(self, handler):
        """启动消费者组"""
        self.running = True
        tasks = []
        for i in range(self.workers):
            tasks.append(self._worker(i, handler))
        await asyncio.gather(*tasks)

    async def _worker(self, worker_id, handler):
        while self.running:
            try:
                msg = await self.queue.get(timeout=3)
                if msg is None:
                    await asyncio.sleep(0.5)
                    continue
                try:
                    await handler(msg["payload"])
                    await self.queue.ack(msg["id"])
                    log.info(f"[{self.group_name}-{worker_id}] ✅ {msg['id']}")
                except Exception as e:
                    await self.queue.nack(msg["id"], str(e), requeue=True)
            except: pass

    def stop(self):
        self.running = False


# 示例
if __name__ == '__main__':
    async def demo():
        q = HAQueue("sensor_data")

        # 生产
        for i in range(10):
            msg_id = await q.put({"device": f"sensor_{i}", "value": i * 10})
            print(f"生产: {msg_id}")

        async def handler(payload):
            print(f"消费: {payload}")
            await asyncio.sleep(0.1)

        # 消费
        group = ConsumerGroup(q, "demo", workers=3)
        await asyncio.wait_for(group.start(handler), timeout=5)
        group.stop()
        print(f"队列统计: {q.stats}")

    asyncio.run(demo())
