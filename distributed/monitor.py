#!/usr/bin/env python3
"""
科为博工业IoT — 分布式系统监控
节点健康检查、数据流延迟监控、系统指标采集、告警引擎
"""
import asyncio, json, time, logging
from datetime import datetime
from collections import deque

logging.basicConfig(level=logging.INFO, format='[MON] %(message)s')
log = logging.getLogger('MON')

class Alert:
    def __init__(self, severity, source, message, metric=None, threshold=None, value=None):
        self.severity = severity  # INFO, WARN, CRITICAL
        self.source = source
        self.message = message
        self.metric = metric
        self.threshold = threshold
        self.value = value
        self.timestamp = datetime.now().isoformat()

    def __repr__(self):
        return f"[{self.severity}] {self.source}: {self.message}"


class MetricCollector:
    """指标采集器"""
    def __init__(self, window_size=60):
        self.window_size = window_size
        self.metrics = {}  # name -> deque of (timestamp, value)

    def record(self, name, value):
        if name not in self.metrics:
            self.metrics[name] = deque(maxlen=self.window_size)
        self.metrics[name].append((time.time(), value))

    def get_rate(self, name, seconds=60):
        """获取指定时间窗内的速率（每秒）"""
        if name not in self.metrics:
            return 0
        cutoff = time.time() - seconds
        recent = [v for t, v in self.metrics[name] if t >= cutoff]
        return len(recent) / seconds if seconds > 0 else 0

    def get_avg(self, name, seconds=60):
        if name not in self.metrics:
            return 0
        cutoff = time.time() - seconds
        recent = [v for t, v in self.metrics[name] if t >= cutoff]
        return sum(recent) / len(recent) if recent else 0

    def get_latest(self, name):
        if name not in self.metrics or not self.metrics[name]:
            return 0
        return self.metrics[name][-1][1]


class AlertEngine:
    """告警规则引擎"""
    def __init__(self):
        self.rules = []
        self.alerts = deque(maxlen=100)

    def add_rule(self, name, metric, operator, threshold, severity, message_template):
        self.rules.append({
            "name": name,
            "metric": metric,
            "operator": operator,   # gt, lt, gte, lte, eq
            "threshold": threshold,
            "severity": severity,
            "message": message_template
        })

    def evaluate(self, metrics):
        """评估所有告警规则"""
        for rule in self.rules:
            if rule["metric"] not in metrics.metrics:
                continue
            metric_name = rule["metric"]
            values = [v for _, v in metrics.metrics[metric_name]]
            if not values:
                continue
            latest = values[-1]
            triggered = False

            if rule["operator"] == "gt" and latest > rule["threshold"]:
                triggered = True
            elif rule["operator"] == "lt" and latest < rule["threshold"]:
                triggered = True
            elif rule["operator"] == "gte" and latest >= rule["threshold"]:
                triggered = True
            elif rule["operator"] == "lte" and latest <= rule["threshold"]:
                triggered = True

            if triggered:
                msg = rule["message"].format(value=latest, threshold=rule["threshold"])
                alert = Alert(rule["severity"], rule["name"], msg, metric_name, rule["threshold"], latest)
                self.alerts.append(alert)
                log.warning(f"🚨 {alert}")

    def get_alerts(self, severity=None):
        if not severity:
            return list(self.alerts)
        return [a for a in self.alerts if a.severity == severity]


class DistributedMonitor:
    """分布式系统监控"""
    def __init__(self, check_interval=5):
        self.metrics = MetricCollector(window_size=120)
        self.alert_engine = AlertEngine()
        self.check_interval = check_interval
        self.nodes = {}           # node_id -> last_heartbeat
        self.stores = {}
        self.queues = {}
        self.running = False
        self._setup_default_rules()

    def _setup_default_rules(self):
        self.alert_engine.add_rule("数据流延迟", "data_lag", "gt", 30, "WARN", "数据延迟 {value}s, 阈值 {threshold}s")
        self.alert_engine.add_rule("队列堆积", "queue_depth", "gt", 1000, "WARN", "队列深度 {value}, 阈值 {threshold}")
        self.alert_engine.add_rule("节点掉线数", "node_failures", "gt", 2, "CRITICAL", "节点故障 {value} 个, 阈值 {threshold}")
        self.alert_engine.add_rule("采集失败率", "collect_failure_rate", "gt", 0.2, "WARN", "采集失败率 {value:.1%}, 阈值 {threshold:.1%}")

    def register_node(self, node_id):
        self.nodes[node_id] = {"last_heartbeat": time.time(), "status": "online", "failures": 0}

    def heartbeat(self, node_id):
        if node_id in self.nodes:
            self.nodes[node_id]["last_heartbeat"] = time.time()
            self.nodes[node_id]["status"] = "online"

    def record_data_lag(self, lag_seconds):
        self.metrics.record("data_lag", lag_seconds)

    def record_queue_depth(self, depth):
        self.metrics.record("queue_depth", depth)

    def record_collect_rate(self, rate):
        self.metrics.record("collect_rate", rate)

    def record_collect_failure(self, success=True):
        self.metrics.record("collect_attempts", 1)
        if not success:
            self.metrics.record("collect_failures", 1)

    def get_collect_failure_rate(self):
        attempts = self.metrics.get_rate("collect_attempts")
        failures = self.metrics.get_rate("collect_failures")
        return failures / attempts if attempts > 0 else 0

    def check_node_health(self, timeout=15):
        now = time.time()
        failures = 0
        for nid, info in self.nodes.items():
            if now - info["last_heartbeat"] > timeout:
                info["status"] = "offline"
                info["failures"] += 1
                failures += 1
            else:
                info["status"] = "online"
        return failures

    async def _monitor_loop(self):
        while self.running:
            try:
                # 节点健康检查
                node_failures = self.check_node_health()
                self.metrics.record("node_failures", node_failures)

                # 评估告警
                self.alert_engine.evaluate(self.metrics)

            except Exception as e:
                log.error(f"监控循环异常: {e}")
            await asyncio.sleep(self.check_interval)

    async def start(self):
        self.running = True
        asyncio.create_task(self._monitor_loop())
        log.info("分布式监控系统启动")

    def stop(self):
        self.running = False

    def get_status(self):
        return {
            "nodes": {nid: {"status": info["status"], "uptime": round(time.time() - info["last_heartbeat"], 1)}
                     for nid, info in self.nodes.items()},
            "metrics": {
                "collect_rate": round(self.metrics.get_rate("collect_rate"), 2),
                "data_lag": round(self.metrics.get_latest("data_lag"), 1),
                "queue_depth": round(self.metrics.get_latest("queue_depth")),
                "node_failures": round(self.metrics.get_latest("node_failures"))
            },
            "alerts": [str(a) for a in self.alert_engine.get_alerts()]
        }


# 示例
async def demo():
    mon = DistributedMonitor(check_interval=3)

    # 注册节点
    for i in range(5):
        mon.register_node(f"collector-{i}")

    await mon.start()

    # 模拟指标数据
    for _ in range(10):
        for i in range(5):
            mon.heartbeat(f"collector-{i}")
        mon.record_data_lag(random.uniform(0, 5))
        mon.record_queue_depth(random.randint(0, 200))
        mon.record_collect_rate(random.uniform(10, 50))
        await asyncio.sleep(1)

    # 模拟故障
    mon.nodes["collector-0"]["last_heartbeat"] -= 20  # 超时离线

    await asyncio.sleep(4)
    log.info(f"系统状态: {json.dumps(mon.get_status(), indent=2, ensure_ascii=False)}")
    mon.stop()

if __name__ == '__main__':
    import random
    asyncio.run(demo())
