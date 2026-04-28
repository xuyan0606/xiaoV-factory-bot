"""
科为博生物科技工厂 — 分布式事务方案
======================================
适用场景: 酶制剂/益生菌/生物发酵产线

实现：
  1. TCC模式      — 适用于采集任务分配（资源预留型）
  2. SAGA模式     — 适用于批次生产流程（长事务）
  3. 最终一致性   — 基于消息队列
  4. 幂等性检查   — 通用去重机制

设计原则：
  - 零外部依赖，仅使用 Python 标准库
  - 可集成到已有 distributed/ 模块
  - 每个模式可独立运行验证
"""

import abc
import json
import logging
import time
import uuid
from collections import defaultdict
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DistributedTx")


# =============================================================================
# 工具函数 & 基础类型
# =============================================================================

TxnId = str


class TxStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"


@dataclass
class TransactionContext:
    """事务上下文，在整个事务生命周期中传递"""
    txn_id: TxnId
    status: TxStatus = TxStatus.PENDING
    created_at: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self):
        return {
            "txn_id": self.txn_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "payload": self.payload,
            "retry_count": self.retry_count,
        }


def generate_txn_id(prefix: str = "txn") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# =============================================================================
# 幂等性检查
# =============================================================================

class IdempotencyChecker:
    """
    幂等性检查器 — 防止重复执行

    使用内存存储（生产环境应替换为 Redis）
    支持 TTL 自动过期
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl_seconds

    def already_processed(self, idempotency_key: str) -> bool:
        """检查是否已处理过此幂等键"""
        self._evict_expired()
        return idempotency_key in self._store

    def mark_processed(self, idempotency_key: str, result: Any = None):
        """标记幂等键为已处理"""
        self._store[idempotency_key] = {
            "result": result,
            "timestamp": time.time(),
        }

    def get_result(self, idempotency_key: str) -> Optional[Any]:
        """获取已处理的结果"""
        entry = self._store.get(idempotency_key)
        if entry:
            return entry.get("result")
        return None

    def _evict_expired(self):
        now = time.time()
        expired = [
            k for k, v in self._store.items()
            if now - v["timestamp"] > self._ttl
        ]
        for k in expired:
            del self._store[k]

    def clear(self):
        self._store.clear()

    def size(self) -> int:
        return len(self._store)


# 全局幂等性检查器
idempotency_checker = IdempotencyChecker()


def idempotent(func: Callable) -> Callable:
    """
    幂等性装饰器

    用法:
        @idempotent
        def my_operation(txn_ctx):
            ...
    """
    def wrapper(txn_ctx: TransactionContext, *args, **kwargs):
        # 使用 txn_id 作为幂等键
        key = txn_ctx.txn_id
        if idempotency_checker.already_processed(key):
            logger.warning(f"[幂等] 事务 {key} 已执行过，跳过")
            return idempotency_checker.get_result(key)
        result = func(txn_ctx, *args, **kwargs)
        idempotency_checker.mark_processed(key, result)
        return result
    return wrapper


# =============================================================================
# TCC 模式 — Try-Confirm/Cancel
# =============================================================================

class TCCException(Exception):
    """TCC 事务异常"""
    pass


class TCCParticipant(abc.ABC):
    """
    TCC 参与者接口

    每个参与者必须实现 Try / Confirm / Cancel 三个方法
    """

    @abc.abstractmethod
    def try_phase(self, txn_ctx: TransactionContext) -> bool:
        """预留资源，返回 True 表示成功"""
        ...

    @abc.abstractmethod
    def confirm_phase(self, txn_ctx: TransactionContext) -> bool:
        """确认执行，返回 True 表示成功"""
        ...

    @abc.abstractmethod
    def cancel_phase(self, txn_ctx: TransactionContext) -> bool:
        """取消/回滚，释放预留资源，返回 True 表示成功"""
        ...


class TCCTransactionManager:
    """
    TCC 事务管理器

    适用于: 采集任务分配、资源预留型场景
    流程: Try -> 全部成功 -> Confirm
          Try -> 部分失败 -> Cancel (全部)
    实现自动补偿: 如果 Confirm 阶段某参与者失败，自动 Cancel 已成功的参与者
    """

    def __init__(self, txn_id: TxnId, participants: List[TCCParticipant]):
        self.txn_id = txn_id
        self.participants = participants
        self._confirmed: List[TCCParticipant] = []
        self._context = TransactionContext(txn_id=txn_id)

    def execute(self, payload: Dict[str, Any] = None) -> TransactionContext:
        """
        执行 TCC 事务

        Args:
            payload: 业务负载参数

        Returns:
            事务上下文，包含最终状态
        """
        if payload:
            self._context.payload = payload

        logger.info(f"[TCC] 开始事务 {self.txn_id}")

        # Phase 1: Try
        try_results = []
        for p in self.participants:
            try:
                ok = p.try_phase(self._context)
                try_results.append(ok)
                logger.info(f"[TCC] Try阶段: {p.__class__.__name__} -> {'OK' if ok else 'FAIL'}")
            except Exception as e:
                logger.error(f"[TCC] Try阶段异常: {p.__class__.__name__}: {e}")
                try_results.append(False)

        if all(try_results):
            # Phase 2: Confirm
            try:
                self._do_confirm()
                self._context.status = TxStatus.SUCCESS
                logger.info(f"[TCC] 事务 {self.txn_id} 完成 (Confirm)")
            except Exception as e:
                logger.error(f"[TCC] Confirm阶段失败: {e}")
                self._context.status = TxStatus.FAILED
                self._do_cancel()
        else:
            # Phase 2: Cancel (补偿)
            logger.warning(f"[TCC] Try阶段有失败，执行Cancel补偿")
            self._context.status = TxStatus.CANCELLED
            self._do_cancel()

        self._context.retry_count += 1
        return self._context

    def _do_confirm(self):
        """执行确认阶段"""
        for p in self.participants:
            ok = p.confirm_phase(self._context)
            if ok:
                self._confirmed.append(p)
            else:
                raise TCCException(f"Confirm失败: {p.__class__.__name__}")

    def _do_cancel(self):
        """执行取消/补偿阶段"""
        self._context.status = TxStatus.COMPENSATING
        for p in reversed(self.participants):  # 反向顺序回滚
            try:
                p.cancel_phase(self._context)
                logger.info(f"[TCC] Cancel: {p.__class__.__name__} OK")
            except Exception as e:
                logger.error(f"[TCC] Cancel异常: {p.__class__.__name__}: {e}")


# ---- TCC 示例实现 ----

class CollectionTaskAllocator(TCCParticipant):
    """
    采集任务分配 — Try预留采集资源，Confirm下发任务，Cancel释放资源

    模拟场景: 将采集任务分配给边缘网关
    """

    def __init__(self, name: str, task_capacity: int = 5):
        self.name = name
        self.task_capacity = task_capacity
        self._reserved = 0
        self._tasks: List[str] = []

    def try_phase(self, txn_ctx: TransactionContext) -> bool:
        task_count = txn_ctx.payload.get("task_count", 1)
        if self._reserved + task_count <= self.task_capacity:
            self._reserved += task_count
            txn_ctx.payload[f"{self.name}_reserved"] = task_count
            logger.info(f"  {self.name}: 预留 {task_count} 个采集任务 (已用 {self._reserved}/{self.task_capacity})")
            return True
        logger.warning(f"  {self.name}: 容量不足 (已用 {self._reserved}/{self.task_capacity})")
        return False

    def confirm_phase(self, txn_ctx: TransactionContext) -> bool:
        task_ids = txn_ctx.payload.get("task_ids", [])
        for tid in task_ids:
            self._tasks.append(tid)
        logger.info(f"  {self.name}: 确认下发 {len(task_ids)} 个任务")
        return True

    def cancel_phase(self, txn_ctx: TransactionContext) -> bool:
        reserved = txn_ctx.payload.get(f"{self.name}_reserved", 0)
        self._reserved -= reserved
        logger.info(f"  {self.name}: 释放 {reserved} 个资源")
        return True


class DataChannelReserver(TCCParticipant):
    """
    数据通道预留 — 预留 MQTT Topic / Kafka Partition
    """

    def __init__(self, name: str, max_channels: int = 10):
        self.name = name
        self.max_channels = max_channels
        self._used_channels = 0

    def try_phase(self, txn_ctx: TransactionContext) -> bool:
        channels_needed = txn_ctx.payload.get("channels", 1)
        if self._used_channels + channels_needed <= self.max_channels:
            self._used_channels += channels_needed
            logger.info(f"  {self.name}: 预留 {channels_needed} 个通道 (已用 {self._used_channels}/{self.max_channels})")
            return True
        return False

    def confirm_phase(self, txn_ctx: TransactionContext) -> bool:
        logger.info(f"  {self.name}: 通道分配确认")
        return True

    def cancel_phase(self, txn_ctx: TransactionContext) -> bool:
        channels = txn_ctx.payload.get("channels", 1)
        self._used_channels -= channels
        logger.info(f"  {self.name}: 释放 {channels} 个通道")
        return True


# =============================================================================
# SAGA 模式
# =============================================================================

class SagaStep(abc.ABC):
    """
    SAGA 步骤

    每个步骤包含:
      - execute: 正向操作
      - compensate: 补偿操作 (回滚)
    """

    @abc.abstractmethod
    def execute(self, ctx: TransactionContext) -> bool:
        ...

    @abc.abstractmethod
    def compensate(self, ctx: TransactionContext) -> bool:
        ...


class SagaCoordinator:
    """
    SAGA 协调器 — 适用于批次生产流程等长事务

    执行策略:
      - 正向: 按顺序执行每个步骤
      - 补偿: 失败时按反向顺序执行补偿

    适用于:
      - 批次生产流程 (配料→接种→发酵→离心→干燥→包装)
      - 跨服务编排
    """

    def __init__(self, txn_id: TxnId, steps: List[SagaStep]):
        self.txn_id = txn_id
        self.steps = steps
        self._executed_steps: List[int] = []  # 已成功执行的步骤索引
        self._context = TransactionContext(txn_id=txn_id)

    def execute(self, payload: Dict[str, Any] = None) -> TransactionContext:
        if payload:
            self._context.payload = payload

        logger.info(f"[SAGA] 开始事务 {self.txn_id} ({len(self.steps)} steps)")

        # 正向执行
        for i, step in enumerate(self.steps):
            try:
                ok = step.execute(self._context)
                if ok:
                    self._executed_steps.append(i)
                    logger.info(f"  Step {i}: {step.__class__.__name__} -> OK")
                else:
                    logger.error(f"  Step {i}: {step.__class__.__name__} -> FAILED")
                    self._compensate(i)
                    self._context.status = TxStatus.FAILED
                    return self._context
            except Exception as e:
                logger.error(f"  Step {i}: {step.__class__.__name__} 异常: {e}")
                self._compensate(i)
                self._context.status = TxStatus.FAILED
                return self._context

        self._context.status = TxStatus.SUCCESS
        logger.info(f"[SAGA] 事务 {self.txn_id} 完成")
        return self._context

    def _compensate(self, failed_step_index: int):
        """反向补偿已执行成功的步骤"""
        logger.warning(f"[SAGA] 开始补偿 (失败步骤: {failed_step_index})")
        self._context.status = TxStatus.COMPENSATING

        # 反向遍历已执行成功的步骤
        for i in reversed(self._executed_steps):
            if i >= failed_step_index:
                continue  # 跳过失败步骤本身及之后的
            step = self.steps[i]
            try:
                ok = step.compensate(self._context)
                logger.info(f"  补偿 Step {i}: {step.__class__.__name__} -> {'OK' if ok else 'FAIL'}")
            except Exception as e:
                logger.error(f"  补偿 Step {i} 异常: {e}")


# ---- SAGA 示例实现: 批次生产流程 ----

class BatchCreateStep(SagaStep):
    """创建批次记录"""

    def execute(self, ctx: TransactionContext) -> bool:
        batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
        ctx.payload["batch_id"] = batch_id
        ctx.payload["batch_status"] = "created"
        logger.info(f"  [批次创建] batch_id={batch_id}")
        return True

    def compensate(self, ctx: TransactionContext) -> bool:
        batch_id = ctx.payload.get("batch_id", "?")
        ctx.payload["batch_status"] = "cancelled"
        logger.info(f"  [批次取消] batch_id={batch_id}")
        return True


class MaterialDispenseStep(SagaStep):
    """物料配料"""

    def __init__(self, material_store: Dict[str, int]):
        self._store = material_store

    def execute(self, ctx: TransactionContext) -> bool:
        recipe = ctx.payload.get("recipe", {})
        reserved: Dict[str, int] = {}
        for mat, qty in recipe.items():
            if self._store.get(mat, 0) >= qty:
                self._store[mat] -= qty
                reserved[mat] = qty
            else:
                # 回滚已扣减的物料
                for m, q in reserved.items():
                    self._store[m] += q
                logger.error(f"  [配料] {mat} 库存不足 (需要 {qty}, 剩余 {self._store.get(mat, 0)})")
                return False
        ctx.payload["reserved_materials"] = reserved
        ctx.payload["batch_status"] = "dispensed"
        logger.info(f"  [配料] 完成: {reserved}")
        return True

    def compensate(self, ctx: TransactionContext) -> bool:
        reserved = ctx.payload.get("reserved_materials", {})
        for mat, qty in reserved.items():
            self._store[mat] = self._store.get(mat, 0) + qty
        ctx.payload["batch_status"] = "materials_returned"
        logger.info(f"  [配料返还] 归还物料: {reserved}")
        return True


class FermentationStep(SagaStep):
    """发酵工序"""

    def execute(self, ctx: TransactionContext) -> bool:
        if ctx.payload.get("batch_status") != "dispensed":
            logger.error("  [发酵] 前置条件不满足: 未配料")
            return False
        ctx.payload["batch_status"] = "fermenting"
        ctx.payload["fermentation_start"] = time.time()
        logger.info("  [发酵] 开始发酵")
        return True

    def compensate(self, ctx: TransactionContext) -> bool:
        ctx.payload["batch_status"] = "fermentation_cancelled"
        logger.info("  [发酵] 终止发酵 (批次废弃)")
        return True


class CentrifugeStep(SagaStep):
    """离心工序"""

    def execute(self, ctx: TransactionContext) -> bool:
        if ctx.payload.get("batch_status") not in ("fermenting",):
            # 实际中发酵需要完成，这里简化
            ctx.payload["batch_status"] = "centrifuged"
            logger.info("  [离心] 完成离心分离")
            return True
        return True

    def compensate(self, ctx: TransactionContext) -> bool:
        ctx.payload["batch_status"] = "centrifuge_cancelled"
        logger.info("  [离心] 终止离心")
        return True


class DryingStep(SagaStep):
    """干燥工序"""

    def execute(self, ctx: TransactionContext) -> bool:
        ctx.payload["batch_status"] = "dried"
        logger.info("  [干燥] 完成喷雾干燥")
        return True

    def compensate(self, ctx: TransactionContext) -> bool:
        ctx.payload["batch_status"] = "drying_cancelled"
        logger.info("  [干燥] 终止干燥 (中间产物待处理)")
        return True


class PackagingStep(SagaStep):
    """包装工序"""

    def execute(self, ctx: TransactionContext) -> bool:
        ctx.payload["batch_status"] = "packaged"
        ctx.payload["completed_at"] = time.time()
        logger.info("  [包装] 完成包装")
        return True

    def compensate(self, ctx: TransactionContext) -> bool:
        ctx.payload["batch_status"] = "packaging_cancelled"
        logger.info("  [包装] 终止包装")
        return True


# =============================================================================
# 最终一致性方案 — 基于消息队列
# =============================================================================

class Message:
    """消息体"""

    def __init__(self, topic: str, payload: Dict[str, Any],
                 msg_id: str = None, txn_id: str = None):
        self.msg_id = msg_id or uuid.uuid4().hex
        self.topic = topic
        self.payload = payload
        self.txn_id = txn_id
        self.created_at = time.time()
        self.retry_count = 0
        self.max_retries = 5

    def to_dict(self) -> Dict:
        return {
            "msg_id": self.msg_id,
            "topic": self.topic,
            "payload": self.payload,
            "txn_id": self.txn_id,
            "created_at": self.created_at,
            "retry_count": self.retry_count,
        }


class MessageQueue:
    """
    内存消息队列 — 模拟消息中间件

    生产环境应替换为 Kafka / RocketMQ / RabbitMQ
    """

    def __init__(self):
        self._queues: Dict[str, List[Message]] = defaultdict(list)
        self._dead_letter: List[Message] = []

    def publish(self, topic: str, payload: Dict[str, Any],
                txn_id: str = None) -> str:
        msg = Message(topic=topic, payload=payload, txn_id=txn_id)
        self._queues[topic].append(msg)
        logger.info(f"[MQ] 发布消息 topic={topic} msg_id={msg.msg_id}")
        return msg.msg_id

    def consume(self, topic: str, batch_size: int = 1) -> List[Message]:
        messages = self._queues.get(topic, [])
        batch = messages[:batch_size]
        self._queues[topic] = messages[batch_size:]
        return batch

    def requeue(self, msg: Message, delay_seconds: int = 1):
        """重新入队 (重试)"""
        if msg.retry_count >= msg.max_retries:
            self._dead_letter.append(msg)
            logger.warning(f"[MQ] 消息 {msg.msg_id} 已达最大重试次数, 移入死信队列")
            return
        msg.retry_count += 1
        # 模拟延迟重试，实际应使用定时消息
        self._queues[msg.topic].append(msg)
        logger.info(f"[MQ] 消息 {msg.msg_id} 重试 #{msg.retry_count}")

    def dead_letter_count(self) -> int:
        return len(self._dead_letter)

    def queue_size(self, topic: str = None) -> int:
        if topic:
            return len(self._queues.get(topic, []))
        return sum(len(q) for q in self._queues.values())


class EventualConsistencyCoordinator:
    """
    最终一致性协调器

    流程:
      1. 本地事务执行
      2. 消息发布到 MQ
      3. 下游服务消费消息并执行
      4. 失败自动重试 (最多 N 次)
      5. 超过重试次数进死信队列 (人工处理)

    适用于:
      - 设备状态变更通知
      - 批次状态流转通知
      - 报表/数据分析异步更新
    """

    def __init__(self, message_queue: MessageQueue):
        self.mq = message_queue
        self._handlers: Dict[str, Callable] = {}

    def register_handler(self, topic: str, handler: Callable[[Dict], bool]):
        """注册消息处理器"""
        self._handlers[topic] = handler

    def publish_event(self, topic: str, txn_id: str,
                      payload: Dict[str, Any]) -> str:
        """
        发布事件 (本地事务完成后调用)
        使用 txn_id 确保幂等
        """
        payload["_txn_id"] = txn_id
        return self.mq.publish(topic, payload, txn_id)

    def process_messages(self, topic: str, batch_size: int = 5):
        """
        处理消息队列中的消息
        返回: (成功数, 失败数)
        """
        if topic not in self._handlers:
            logger.warning(f"[EC] 无处理器注册 topic={topic}")
            return (0, 0)

        handler = self._handlers[topic]
        messages = self.mq.consume(topic, batch_size)
        success = 0
        failed = 0

        for msg in messages:
            try:
                # 幂等检查
                txn_id = msg.payload.get("_txn_id", msg.txn_id)
                if txn_id and idempotency_checker.already_processed(txn_id):
                    logger.info(f"[EC] 幂等跳过: {txn_id}")
                    success += 1
                    continue

                result = handler(msg.payload)
                if result:
                    if txn_id:
                        idempotency_checker.mark_processed(txn_id, result)
                    success += 1
                else:
                    self.mq.requeue(msg)
                    failed += 1
            except Exception as e:
                logger.error(f"[EC] 处理异常: {e}")
                self.mq.requeue(msg)
                failed += 1

        return (success, failed)


# =============================================================================
# 验证 & 示例运行
# =============================================================================

def demo_tcc():
    """TCC 模式演示 — 采集任务分配"""
    print("\n" + "=" * 60)
    print("TCC 模式演示: 采集任务分配")
    print("=" * 60)

    allocator1 = CollectionTaskAllocator("网关-A", task_capacity=3)
    allocator2 = CollectionTaskAllocator("网关-B", task_capacity=2)
    channel_reserver = DataChannelReserver("MQTT通道", max_channels=5)

    txn_id = generate_txn_id("tcc")
    manager = TCCTransactionManager(txn_id, [allocator1, allocator2, channel_reserver])

    ctx = manager.execute({
        "task_count": 2,
        "channels": 2,
        "task_ids": [f"task_{i}" for i in range(2)],
    })

    print(f"  结果: status={ctx.status.value}, txn_id={ctx.txn_id}")
    print(f"  网关-A reserved={allocator1._reserved}, tasks={allocator1._tasks}")

    # 模拟 Try 失败场景
    print("\n  --- Try阶段失败场景 ---")
    txn_id2 = generate_txn_id("tcc")
    manager2 = TCCTransactionManager(txn_id2, [
        CollectionTaskAllocator("网关-C", task_capacity=1),
        CollectionTaskAllocator("网关-D", task_capacity=0),  # 容量为0，会失败
    ])
    ctx2 = manager2.execute({"task_count": 1, "channels": 1, "task_ids": ["task_x"]})
    print(f"  结果: status={ctx2.status.value} (预期: cancelled)")


def demo_saga():
    """SAGA 模式演示 — 批次生产流程"""
    print("\n" + "=" * 60)
    print("SAGA 模式演示: 批次生产流程")
    print("=" * 60)

    # 库存
    material_store = {
        "葡萄糖": 500,
        "酵母粉": 100,
        "微量元素": 50,
        "消泡剂": 20,
    }

    recipe = {"葡萄糖": 100, "酵母粉": 20, "微量元素": 5, "消泡剂": 2}

    steps = [
        BatchCreateStep(),
        MaterialDispenseStep(material_store),
        FermentationStep(),
        CentrifugeStep(),
        DryingStep(),
        PackagingStep(),
    ]

    txn_id = generate_txn_id("saga")
    coordinator = SagaCoordinator(txn_id, steps)
    ctx = coordinator.execute({
        "recipe": recipe,
        "product": "酶制剂-A",
        "quantity": 1000,
    })

    print(f"  结果: status={ctx.status.value}")
    print(f"  批次: {ctx.payload.get('batch_id', 'N/A')}")
    print(f"  状态: {ctx.payload.get('batch_status', 'N/A')}")
    print(f"  库存剩余: {material_store}")

    # 模拟库存不足失败场景
    print("\n  --- 库存不足失败场景 ---")
    material_store2 = {"葡萄糖": 5, "酵母粉": 0, "微量元素": 0, "消泡剂": 0}
    steps2 = [
        BatchCreateStep(),
        MaterialDispenseStep(material_store2),
    ]
    txn_id2 = generate_txn_id("saga")
    coordinator2 = SagaCoordinator(txn_id2, steps2)
    ctx2 = coordinator2.execute({"recipe": {"葡萄糖": 100, "酵母粉": 50}})
    print(f"  结果: status={ctx2.status.value} (预期: failed)")
    print(f"  库存: {material_store2} (配料失败，应已回滚)")


def demo_eventual_consistency():
    """最终一致性演示 — 基于消息队列"""
    print("\n" + "=" * 60)
    print("最终一致性演示: 设备状态变更通知")
    print("=" * 60)

    mq = MessageQueue()
    coordinator = EventualConsistencyCoordinator(mq)

    # 注册处理器: 设备状态变更
    def device_status_handler(payload: Dict) -> bool:
        device_id = payload.get("device_id")
        status = payload.get("status")
        logger.info(f"  [处理] 设备 {device_id} 状态变更 -> {status}")
        # 模拟处理成功
        return True

    coordinator.register_handler("device.status", device_status_handler)

    # 模拟设备状态变更
    events = [
        {"device_id": "FER-001", "status": "running", "temp": 37.2},
        {"device_id": "FER-002", "status": "alarm", "temp": 42.5},
        {"device_id": "FER-003", "status": "idle", "temp": 25.0},
    ]

    for evt in events:
        txn_id = generate_txn_id("ec")
        coordinator.publish_event("device.status", txn_id, evt)

    print(f"  MQ 队列大小: {mq.queue_size('device.status')}")

    # 处理消息
    success, failed = coordinator.process_messages("device.status", batch_size=5)
    print(f"  处理结果: 成功={success}, 失败={failed}")
    print(f"  死信队列: {mq.dead_letter_count()}")


def demo_idempotency():
    """幂等性演示"""
    print("\n" + "=" * 60)
    print("幂等性检查演示")
    print("=" * 60)

    checker = IdempotencyChecker(ttl_seconds=3600)

    # 第一次执行
    key = "idempotent_key_001"
    print(f"  首次检查 '{key}': {checker.already_processed(key)} (预期: False)")
    checker.mark_processed(key, "result_ok")
    print(f"  再次检查 '{key}': {checker.already_processed(key)} (预期: True)")
    print(f"  获取结果: {checker.get_result(key)} (预期: result_ok)")

    # 装饰器演示
    print("\n  --- @idempotent 装饰器 ---")

    @idempotent
    def process_collection_task(txn_ctx: TransactionContext) -> str:
        logger.info(f"  执行采集任务: {txn_ctx.txn_id}")
        return f"done_{txn_ctx.txn_id}"

    ctx1 = TransactionContext(txn_id="demo_001")
    result1 = process_collection_task(ctx1)
    print(f"  第一次执行结果: {result1}")

    ctx2 = TransactionContext(txn_id="demo_001")  # 相同 txn_id
    result2 = process_collection_task(ctx2)
    print(f"  第二次执行结果: {result2} (预期与第一次相同, 实际未执行)")

    idempotency_checker.clear()


def run_all_demos():
    """运行所有演示"""
    print("\n" + "#" * 60)
    print("# 科为博生物科技工厂 — 分布式事务方案验证")
    print("#" * 60)

    demo_tcc()
    demo_saga()
    demo_eventual_consistency()
    demo_idempotency()

    print("\n" + "=" * 60)
    print("所有演示完成")
    print("=" * 60)


if __name__ == "__main__":
    run_all_demos()
