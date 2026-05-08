"""
MES 传感器模拟器 + WebSocket 推送
模拟发酵罐传感器数据 → Flask-SocketIO → 前端实时曲线

第2阶段核心：数据流贯通
"""

import json
import random
import threading
import time
import datetime
from flask import Flask
from flask_socketio import SocketIO, emit

# ─────────────────────────────────────────
# Flask-SocketIO 服务
# ─────────────────────────────────────────

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mes-secret-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 当前活跃批次的传感器状态
SIM_STATE = {}  # batch_id -> {temp, pH, DO, stir_speed, pressure, trend}

TREND = {}  # 趋势方向

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def next_val(current, lo, hi, volatility=0.5):
    """生成下一个传感器值，带随机游走趋势"""
    trend = TREND.get(id(current), 0)
    # 30%概率反转趋势
    if random.random() < 0.3:
        trend = -trend
    TREND[id(current)] = trend

    delta = random.gauss(trend * 0.3, volatility)
    return clamp(current + delta, lo, hi)

def simulate_batch(batch_id, stage="fermentation"):
    """模拟一个批次的传感器数据流"""
    if stage == "fermentation":
        base = {"temp": 36.5, "pH": 6.5, "DO": 85.0, "stir_speed": 150.0, "pressure": 1.0}
        lo   = {"temp": 34.0, "pH": 5.5, "DO": 60.0, "stir_speed": 100.0, "pressure": 0.8}
        hi   = {"temp": 38.0, "pH": 7.0, "DO": 95.0, "stir_speed": 200.0, "pressure": 1.2}
    elif stage == "seed":
        base = {"temp": 35.0, "pH": 6.2, "DO": 70.0, "stir_speed": 120.0, "pressure": 0.9}
        lo   = {"temp": 33.0, "pH": 5.8, "DO": 50.0, "stir_speed": 80.0,  "pressure": 0.7}
        hi   = {"temp": 37.0, "pH": 6.8, "DO": 85.0, "stir_speed": 160.0, "pressure": 1.1}
    else:
        base = {"temp": 36.0, "pH": 6.0, "DO": 80.0, "stir_speed": 140.0, "pressure": 1.0}
        lo   = {"temp": 34.0, "pH": 5.5, "DO": 60.0, "stir_speed": 100.0, "pressure": 0.8}
        hi   = {"temp": 38.0, "pH": 7.0, "DO": 95.0, "stir_speed": 180.0, "pressure": 1.2}

    SIM_STATE[batch_id] = base.copy()

    while batch_id in SIM_STATE:
        # 每 2 秒推送一次
        time.sleep(2)
        if batch_id not in SIM_STATE:
            break

        row = {}
        for key in base:
            SIM_STATE[batch_id][key] = next_val(
                SIM_STATE[batch_id][key], lo[key], hi[key], volatility=0.3
            )
            row[key] = round(SIM_STATE[batch_id][key], 2)

        # 计算超限告警
        alerts = []
        if row["temp"] > 37.5:
            alerts.append({"type": "temp_high", "level": "critical", "value": row["temp"]})
        if row["pH"] > 6.8 or row["pH"] < 5.8:
            alerts.append({"type": "pH_abnormal", "level": "warning", "value": row["pH"]})
        if row["DO"] < 30:
            alerts.append({"type": "DO_low", "level": "critical", "value": row["DO"]})

        payload = {
            "batch_id": batch_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "params": row,
            "alerts": alerts
        }

        # 推送到前端
        socketio.emit("batch_params", payload, namespace="/mes")
        print(f"[SIM] {batch_id} → T={row['temp']} pH={row['pH']} DO={row['DO']} | alerts={len(alerts)}")

def start_simulation(batch_id, stage="fermentation"):
    """启动某批次的模拟线程"""
    t = threading.Thread(target=simulate_batch, args=(batch_id, stage), daemon=True)
    t.start()
    return t

# ─────────────────────────────────────────
# WebSocket 事件
# ─────────────────────────────────────────

@socketio.on("connect", namespace="/mes")
def on_connect():
    print(f"[WS] 客户端连接: {request.sid if 'request' in dir() else 'unknown'}")
    emit("connected", {"status": "ok"})

@socketio.on("disconnect", namespace="/mes")
def on_disconnect():
    print("[WS] 客户端断开")

@socketio.on("subscribe_batch", namespace="/mes")
def on_subscribe(data):
    """前端订阅某批次实时数据"""
    batch_id = data.get("batch_id")
    if batch_id and batch_id not in SIM_STATE:
        start_simulation(batch_id)
    emit("subscribed", {"batch_id": batch_id})

@socketio.on("unsubscribe_batch", namespace="/mes")
def on_unsubscribe(data):
    batch_id = data.get("batch_id")
    if batch_id in SIM_STATE:
        del SIM_STATE[batch_id]

# ─────────────────────────────────────────
# 主动推送告警（当参数超限时）
# ─────────────────────────────────────────

def push_alert(batch_id, alert_type, level, message, value, threshold):
    socketio.emit("alert", {
        "batch_id": batch_id,
        "alert_type": alert_type,
        "level": level,
        "message": message,
        "value": value,
        "threshold": threshold,
        "timestamp": datetime.datetime.now().isoformat(),
    }, namespace="/mes")

# ─────────────────────────────────────────
# 启动
# ─────────────────────────────────────────

if __name__ == "__main__":
    # 启动默认模拟批次
    start_simulation("BAT-20260502-001", "fermentation")
    print("[MES-WS] WebSocket 服务启动在 ws://localhost:5002/mes")
    socketio.run(app, host="0.0.0.0", port=5002, debug=False, use_reloader=False)
