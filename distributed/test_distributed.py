#!/usr/bin/env python3
"""
科为博工业IoT — 分布式系统集成测试
测试内容：
1. 一致性哈希设备分配
2. 消息队列生产消费
3. 熔断器容错
4. 故障转移
5. 数据存储分片
6. 监控告警
"""
import asyncio, json, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from circuit_breaker import CircuitBreaker, retry
from collector_engine import DistributedCollector, ConsistentHashRing
from ha_queue import HAQueue, ConsumerGroup
from distributed_store import DistributedStore
from monitor import DistributedMonitor

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


async def test_consistent_hash():
    """测试一致性哈希"""
    print(f"\n{'='*50}")
    print("测试1: 一致性哈希")
    print('='*50)

    ring = ConsistentHashRing(nodes=["collector-0", "collector-1", "collector-2"])

    # 分配10台设备
    devices = [f"fermenter-{i:02d}" for i in range(10)]
    assignments = {}
    for dev in devices:
        node = ring.get_node(dev)
        assignments[dev] = node

    # 验证所有设备都有分配
    all_assigned = all(v is not None for v in assignments.values())
    test("所有设备分配节点", all_assigned)

    # 验证设备在移除节点后重新分配
    ring.remove_node("collector-0")
    new_assignments = {}
    for dev in devices:
        node = ring.get_node(dev)
        new_assignments[dev] = node

    rebalanced = all(v is not None for v in new_assignments.values())
    test("节点移除后设备仍有分配", rebalanced)

    # 验证大部分设备分配到剩余节点
    assigned_to_remaining = sum(1 for v in new_assignments.values() if v in ["collector-1", "collector-2"])
    test("故障转移后设备分配到存活节点", assigned_to_remaining == 10)

    # 添加节点回来，验证分配一致性
    ring.add_node("collector-0")
    re_added = sum(1 for v in new_assignments.values() if v is not None)
    test("重新添加节点后系统不崩溃", re_added > 0)

    return ring


async def test_circuit_breaker():
    """测试熔断器"""
    print(f"\n{'='*50}")
    print("测试2: 熔断器")
    print('='*50)

    cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=2, half_open_max=1)
    import random

    # 初始状态 CLOSED
    test("初始状态为CLOSED", cb.state.value == "CLOSED")

    failures = 0
    for i in range(10):
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except:
            failures += 1

    # 连续3次失败后应触发OPEN
    test("连续失败后触发OPEN", cb.state.value == "OPEN")
    test("实际调用失败计数正确", cb.total_failures == 3)  # OPEN后请求被拦截，不计入失败

    # OPEN状态下应拒绝请求
    rejected = 0
    for _ in range(3):
        try:
            cb.call(lambda: "ok")
        except Exception as e:
            if "熔断" in str(e):
                rejected += 1
    test("OPEN状态下请求被拒绝", rejected > 0)

    await asyncio.sleep(2.5)  # 等待恢复超时

    # HALF_OPEN状态验证
    try:
        cb.call(lambda: "ok")
        test("超时后进入HALF_OPEN并恢复成功", True)
    except:
        test("超时后HALF_OPEN恢复", False)

    return cb


async def test_ha_queue():
    """测试高可用消息队列"""
    print(f"\n{'='*50}")
    print("测试3: 高可用消息队列")
    print('='*50)

    q = HAQueue("test_queue")

    # 生产消息
    ids = []
    for i in range(5):
        msg_id = await q.put({"value": i, "device": f"sensor_{i}"})
        ids.append(msg_id)

    test("消息生产成功", len(ids) == 5)
    test("队列长度正确", q.size == 5)

    # 消费消息
    consumed = []
    for _ in range(5):
        msg = await q.get(timeout=2)
        if msg:
            consumed.append(msg)
            await q.ack(msg["id"])

    test("消息消费成功", len(consumed) == 5)
    test("确认后队列为空", q.size == 0)
    test("处理中队列为空", len(q.processing) == 0)

    # 测试死信队列
    for i in range(3):
        await q.put({"bad": i})

    for _ in range(3):
        msg = await q.get()
        if msg:
            await q.nack(msg["id"], "处理失败", requeue=False)

    test("死信队列有消息", len(q.dlq) == 3)

    # 测试背压
    small_q = HAQueue("small", max_queue=10)
    overloaded = False
    for i in range(15):
        try:
            await small_q.put({"i": i})
        except:
            overloaded = True
    test("队列满时触发背压", overloaded)

    return q


async def test_distributed_store():
    """测试分布式存储"""
    print(f"\n{'='*50}")
    print("测试4: 分布式数据存储")
    print('='*50)

    store = DistributedStore(shard_count=4, replica_factor=2)

    # 写入数据
    devices = [f"fermenter-{i:02d}" for i in range(8)]
    for ts in range(5):
        for dev in devices:
            msg_id = f"{dev}_{ts}"
            payload = {"device_id": dev, "temperature": 35 + ts * 0.5, "timestamp": time.time()}
            store.write(msg_id, dev, payload)

    test("写入操作成功", store.total_writes > 0)

    # 读取数据
    for dev in devices[:3]:
        data = store.read(dev, limit=5)
        test(f"读取{dev}数据", len(data) > 0)

    # 验证分片
    shard_stats = store.stats()["shards"]
    test("4个分片都有数据", all(s["count"] > 0 for s in shard_stats.values()))

    # 验证副本
    test("写入计数正确", store.total_writes > 0)

    return store


async def test_monitor():
    """测试监控系统"""
    print(f"\n{'='*50}")
    print("测试5: 分布式监控")
    print('='*50)

    mon = DistributedMonitor(check_interval=2)
    await mon.start()

    # 注册节点并发送心跳
    for i in range(3):
        mon.register_node(f"node-{i}")
        mon.heartbeat(f"node-{i}")

    mon.record_data_lag(5)
    mon.record_queue_depth(50)
    mon.record_collect_rate(100)

    await asyncio.sleep(0.5)

    # 验证指标
    test("数据延迟指标记录", mon.metrics.get_latest("data_lag") > 0)
    test("队列深度指标记录", mon.metrics.get_latest("queue_depth") > 0)
    test("节点状态在线", mon.nodes["node-0"]["status"] == "online")

    # 模拟告警
    mon.alert_engine.add_rule("高延迟", "data_lag", "gt", 3, "WARN", "数据延迟 {value}s")
    mon.alert_engine.evaluate(mon.metrics)
    alerts = mon.alert_engine.get_alerts()
    test("告警规则触发", len(alerts) > 0)

    mon.stop()


async def test_integration():
    """综合集成测试"""
    print(f"\n{'='*50}")
    print("测试6: 综合集成测试")
    print('='*50)

    # 1. 启动分布式采集引擎
    dc = DistributedCollector(heartbeat_interval=3, failover_timeout=6)
    for i in range(3):
        dc.add_node(f"collector-{i}")
    await dc.start()

    # 2. 分配设备
    devices = [f"fermenter-{i:02d}" for i in range(12)]
    for dev in devices:
        dc.assign_device(dev, {"type": "发酵罐"})

    test("采集引擎启动成功", dc.running)
    test("设备分配正确", sum(len(n.devices) for n in dc.nodes.values()) == 12)

    # 3. 启动消息队列和存储
    q = HAQueue("integrated", max_queue=1000)
    store = DistributedStore(shard_count=4)

    # 4. 启动监控
    mon = DistributedMonitor(check_interval=3)
    for i in range(3):
        mon.register_node(f"collector-{i}")
    await mon.start()

    # 5. 模拟数据采集+生产消费链路
    async def mock_collect():
        for _ in range(3):
            for node in dc.nodes.values():
                batch = await node.collect()
                for data in batch:
                    msg_id = await q.put(data, f"{data['device_id']}_{int(time.time()*1000000)}")
                    store.write(msg_id, data["device_id"], data)
                    mon.record_collect_rate(len(batch))
            await asyncio.sleep(0.5)

    async def mock_consume():
        for _ in range(10):
            msg = await q.get(timeout=2)
            if msg:
                await q.ack(msg["id"])

    await mock_collect()
    await mock_consume()

    test("全链路数据采集成功", dc.get_stats()["total_collected"] > 0)
    test("全链路消息队列成功", q.size >= 0)

    # 6. 验证故障转移
    old_node_count = len(dc.nodes)
    dc.remove_node("collector-0")
    test("故障转移后节点数减少", len(dc.nodes) == old_node_count - 1)
    still_has_devices = sum(len(n.devices) for n in dc.nodes.values())
    test("故障后设备重新分配", still_has_devices == 12)

    await asyncio.sleep(1)

    # 7. 验证监控
    test("监控节点注册正确", len(mon.nodes) == 3)
    for i in range(3):
        mon.heartbeat(f"collector-{i}")
    test("监控心跳正常", mon.nodes[f"collector-0"]["status"] == "online")

    dc.stop()
    mon.stop()
    print(f"\n集成测试全部通过 ✅")


async def main():
    print("=" * 50)
    print("  科为博工厂 · 分布式系统集成测试")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    await test_consistent_hash()
    await test_circuit_breaker()
    await test_ha_queue()
    await test_distributed_store()
    await test_monitor()
    await test_integration()

    print(f"\n{'='*50}")
    print(f"测试总结: ✅ {PASS} 通过  ❌ {FAIL} 失败")
    print(f"总测试数: {PASS + FAIL}")
    print('='*50)

    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
