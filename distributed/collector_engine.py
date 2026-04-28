#!/usr/bin/env python3
"""
xiaoV Industrial IoT — 分布式采集引擎
一致性哈希分配设备、心跳检测、故障转移
"""
import asyncio, hashlib, json, time, logging, random
from bisect import bisect_right
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='[COL] %(message)s')
log = logging.getLogger('COLLECTOR')

class ConsistentHashRing:
    """一致性哈希环 — 设备分配到采集节点"""
    def __init__(self, nodes=None, virtual_nodes=150):
        self.virtual_nodes = virtual_nodes
        self.ring = {}       # hash -> node_id
        self.sorted_keys = []
        self.nodes = set()
        if nodes:
            for n in nodes:
                self.add_node(n)

    def _hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node_id):
        self.nodes.add(node_id)
        for i in range(self.virtual_nodes):
            h = self._hash(f"{node_id}:{i}")
            self.ring[h] = node_id
        self.sorted_keys = sorted(self.ring.keys())

    def remove_node(self, node_id):
        if node_id not in self.nodes:
            return
        self.nodes.discard(node_id)
        keys_to_remove = [k for k, v in self.ring.items() if v == node_id]
        for k in keys_to_remove:
            del self.ring[k]
        self.sorted_keys = sorted(self.ring.keys())

    def get_node(self, key):
        """获取key对应的节点"""
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect_right(self.sorted_keys, h)
        if idx == len(self.sorted_keys):
            idx = 0
        return self.ring[self.sorted_keys[idx]]

    def get_replicas(self, key, count=2):
        """获取key对应的N个副本节点"""
        if not self.ring:
            return []
        h = self._hash(key)
        idx = bisect_right(self.sorted_keys, h)
        result = []
        seen = set()
        for i in range(len(self.sorted_keys)):
            pos = (idx + i) % len(self.sorted_keys)
            node = self.ring[self.sorted_keys[pos]]
            if node not in seen:
                seen.add(node)
                result.append(node)
            if len(result) >= count:
                break
        return result


class CollectorNode:
    """单个采集节点"""
    def __init__(self, node_id, port=9000):
        self.node_id = node_id
        self.port = port
        self.alive = True
        self.devices = {}       # device_id -> device_info
        self.buffer = []        # 本地缓存
        self.last_heartbeat = time.time()
        self.collected = 0

    def assign_device(self, device_id, device_info=None):
        self.devices[device_id] = device_info or {"type": "unknown"}
        log.info(f"[{self.node_id}] 分配设备 {device_id}")

    def remove_device(self, device_id):
        self.devices.pop(device_id, None)

    async def collect(self):
        """采集所有分配的设备数据"""
        for dev_id in list(self.devices.keys()):
            data = {
                "device_id": dev_id,
                "value": random.uniform(20, 40),
                "timestamp": datetime.now().isoformat(),
                "collector": self.node_id
            }
            self.buffer.append(data)
            self.collected += 1
        if self.buffer:
            batch = self.buffer[:]
            self.buffer = []
            return batch
        return []

    def heartbeat(self):
        self.last_heartbeat = time.time()

    def is_alive(self, timeout=10):
        return (time.time() - self.last_heartbeat) < timeout

    def __repr__(self):
        return f"<{self.node_id} devices={len(self.devices)} alive={self.alive}>"


class DistributedCollector:
    """分布式采集引擎"""
    def __init__(self, heartbeat_interval=5, failover_timeout=10):
        self.ring = ConsistentHashRing()
        self.nodes = {}           # node_id -> CollectorNode
        self.heartbeat_interval = heartbeat_interval
        self.failover_timeout = failover_timeout
        self.running = False
        self.stop_event = asyncio.Event()

    def add_node(self, node_id, port=9000):
        node = CollectorNode(node_id, port)
        self.nodes[node_id] = node
        self.ring.add_node(node_id)
        log.info(f"添加采集节点: {node_id}")
        # 重分配已有设备
        self._rebalance_devices()
        return node

    def remove_node(self, node_id):
        if node_id not in self.nodes:
            return
        # 获取该节点的设备
        node = self.nodes[node_id]
        devices = list(node.devices.keys())
        self.ring.remove_node(node_id)
        del self.nodes[node_id]
        # 重新分配设备到其他节点
        for dev_id in devices:
            new_node_id = self.ring.get_node(dev_id)
            if new_node_id and new_node_id in self.nodes:
                self.nodes[new_node_id].assign_device(dev_id)
        log.info(f"移除采集节点: {node_id}, {len(devices)}台设备已迁移")

    def assign_device(self, device_id, device_info=None):
        node_id = self.ring.get_node(device_id)
        if node_id and node_id in self.nodes:
            self.nodes[node_id].assign_device(device_id, device_info)
            return node_id
        return None

    def _rebalance_devices(self):
        """重新平衡所有设备的分配"""
        all_devices = {}
        for nid, node in self.nodes.items():
            for did, dinfo in node.devices.items():
                all_devices[did] = dinfo
            node.devices.clear()

        for did, dinfo in all_devices.items():
            self.assign_device(did, dinfo)

    async def _heartbeat_check(self):
        """心跳检测循环"""
        while not self.stop_event.is_set():
            for node_id, node in list(self.nodes.items()):
                node.heartbeat()
                if not node.is_alive(self.failover_timeout):
                    log.warning(f"节点离线: {node_id}, 执行故障转移")
                    self.remove_node(node_id)
            await asyncio.sleep(self.heartbeat_interval)

    async def start(self):
        """启动采集引擎"""
        self.running = True
        self.stop_event.clear()
        asyncio.create_task(self._heartbeat_check())
        log.info("分布式采集引擎启动")

    async def stop(self):
        self.running = False
        self.stop_event.set()
        log.info("采集引擎停止")

    def get_stats(self):
        return {
            "nodes": len(self.nodes),
            "devices": sum(len(n.devices) for n in self.nodes.values()),
            "total_collected": sum(n.collected for n in self.nodes.values()),
            "node_details": {nid: len(n.devices) for nid, n in self.nodes.items()}
        }


# 示例
async def demo():
    dc = DistributedCollector(heartbeat_interval=3, failover_timeout=6)

    # 添加3个采集节点
    for i in range(3):
        dc.add_node(f"collector-{i}", 9000 + i)

    # 分配20台设备
    for i in range(20):
        dc.assign_device(f"fermenter-{i:02d}", {"type": "发酵罐", "location": f"车间A-{i%5+1}"})

    await dc.start()
    log.info(f"分配状态: {dc.get_stats()}")

    # 模拟采集
    for _ in range(3):
        for node in dc.nodes.values():
            batch = await node.collect()
        await asyncio.sleep(1)

    log.info(f"采集统计: {dc.get_stats()}")

    # 模拟节点故障
    log.info("=== 模拟 collector-1 宕机 ===")
    dc.remove_node("collector-1")
    await asyncio.sleep(1)
    log.info(f"故障后状态: {dc.get_stats()}")

    await dc.stop()

if __name__ == '__main__':
    asyncio.run(demo())
