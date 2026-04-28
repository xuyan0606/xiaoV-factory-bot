"""
xiaoV Factory数字化项目 — Prometheus 指标采集模块
为 Flask 应用添加自定义监控指标，用于 Prometheus 抓取

使用方式：
    from monitoring.metrics import init_metrics
    init_metrics(app)

指标清单：
- flask_http_request_total         — 总请求数
- flask_http_request_duration_seconds — 请求延迟（直方图）
- anomaly_detection_count          — 异常检测计数
- mqtt_messages_total              — MQTT 消息总数
- mqtt_connected_clients           — MQTT 客户端连接数
- device_status                    — 设备状态（1=在线，0=离线）
- factory_bot_queries_total        — 机器人查询总数
"""

import time
from functools import wraps
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import request, Response

# ==================== Prometheus 指标定义 ====================

# HTTP 请求计数器
http_request_total = Counter(
    'flask_http_request_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'http_status']
)

# HTTP 请求延迟直方图
http_request_duration = Histogram(
    'flask_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# 异常检测计数
anomaly_detection_count = Counter(
    'anomaly_detection_total',
    'Total anomaly detections',
    ['device', 'anomaly_type']
)

# MQTT 消息计数器
mqtt_messages_total = Counter(
    'mqtt_messages_total',
    'Total MQTT messages processed',
    ['topic', 'qos']
)

# MQTT 客户端连接数
mqtt_connected_clients = Gauge(
    'mqtt_connected_clients',
    'Current number of MQTT connected clients'
)

# 设备状态（1=在线，0=离线）
device_status = Gauge(
    'device_status',
    'Device online status (1=online, 0=offline)',
    ['device_id', 'device_type', 'workshop']
)

# 工厂机器人查询计数器
factory_bot_queries_total = Counter(
    'factory_bot_queries_total',
    'Total factory bot queries',
    ['query_type']
)

# 车间状态 Gauge
workshop_status = Gauge(
    'workshop_status',
    'Workshop operational status (1=running, 0=stopped)',
    ['workshop_name']
)

# 批次活跃数
active_batches = Gauge(
    'active_batches_total',
    'Total number of active production batches'
)

# 系统运行时间
system_uptime_seconds = Gauge(
    'system_uptime_seconds',
    'System uptime in seconds'
)


def init_metrics(app):
    """
    将 Prometheus 指标端点绑定到 Flask 应用
    并为所有路由添加自动指标采集中间件
    """

    # ==================== /metrics 端点 ====================
    @app.route('/metrics')
    def metrics():
        """Prometheus 抓取端点"""
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    # ==================== 自动采集中间件 ====================
    @app.before_request
    def before_request_metrics():
        """记录请求开始时间"""
        request._start_time = time.time()

    @app.after_request
    def after_request_metrics(response):
        """记录请求完成指标"""
        # 跳过 /metrics 自身
        if request.path == '/metrics':
            return response

        # 计算延迟
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            http_request_duration.labels(
                method=request.method,
                endpoint=request.path
            ).observe(duration)

        # 计数
        http_request_total.labels(
            method=request.method,
            endpoint=request.path,
            http_status=response.status_code
        ).inc()

        # 根据路径记录查询类型
        if request.path == '/dingtalk/webhook':
            factory_bot_queries_total.labels(query_type='dingtalk').inc()
        elif request.path == '/chat':
            factory_bot_queries_total.labels(query_type='webchat').inc()
        elif request.path == '/health':
            factory_bot_queries_total.labels(query_type='health').inc()

        return response


def update_device_status(device_id, is_online, device_type='fermenter', workshop='unknown'):
    """更新设备状态指标"""
    device_status.labels(
        device_id=device_id,
        device_type=device_type,
        workshop=workshop
    ).set(1 if is_online else 0)


def update_mqtt_metrics(topic, qos=0, client_count=None):
    """更新 MQTT 相关指标"""
    mqtt_messages_total.labels(topic=topic, qos=str(qos)).inc()
    if client_count is not None:
        mqtt_connected_clients.set(client_count)


def record_anomaly(device, anomaly_type='unknown'):
    """记录异常检测事件"""
    anomaly_detection_count.labels(device=device, anomaly_type=anomaly_type).inc()


def update_workshop_status(workshop_name, is_running):
    """更新车间运行状态"""
    workshop_status.labels(workshop_name=workshop_name).set(1 if is_running else 0)


def update_batch_count(count):
    """更新活跃批次数量"""
    active_batches.set(count)


def update_uptime():
    """更新系统运行时间"""
    import time as _time
    system_uptime_seconds.set(_time.time())
