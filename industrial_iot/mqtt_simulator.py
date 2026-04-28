#!/usr/bin/env python3
"""
科为博工业物联网 — MQTT 模拟数据源
模拟3个发酵罐的传感器数据，发布到MQTT Broker
"""
import asyncio, json, random, time, struct, logging

logging.basicConfig(level=logging.INFO, format='[SIM] %(message)s')
log = logging.getLogger('SIM')

BROKER_HOST = '127.0.0.1'
BROKER_PORT = 1883
FERMENTERS = 3
INTERVAL = 2  # 秒

def build_publish(topic, payload, qos=0):
    """手动构建MQTT PUBLISH报文"""
    topic_enc = topic.encode()
    remaining = 2 + len(topic_enc) + len(payload)
    # 剩余长度编码
    rl = []
    x = remaining
    while True:
        b = x % 128
        x //= 128
        if x > 0: b |= 128
        rl.append(b)
        if x == 0: break
    header = bytes([(0x03 << 4) | (qos << 1)]) + bytes(rl)
    return header + struct.pack('>H', len(topic_enc)) + topic_enc + payload

async def connect_mqtt(reader, writer, client_id="simulator"):
    """手动MQTT CONNECT"""
    # CONNECT报文
    proto_name = b'\x00\x04MQTT'
    proto_level = 4
    flags = 0x02  # clean session
    keepalive = struct.pack('>H', 60)
    cid_enc = client_id.encode()
    cid_len = struct.pack('>H', len(cid_enc))
    remaining = 2 + len(proto_name) + 1 + 1 + 2 + 2 + len(cid_enc)
    rl = []
    x = remaining
    while True:
        b = x % 128; x //= 128
        if x > 0: b |= 128
        rl.append(b)
        if x == 0: break
    packet = bytes([0x10]) + bytes(rl) + proto_name + bytes([proto_level, flags]) + keepalive + cid_len + cid_enc
    writer.write(packet); await writer.drain()
    # 等待CONNACK
    data = await asyncio.wait_for(reader.read(4), timeout=5)
    return data[3] == 0  # return code

async def main():
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(BROKER_HOST, BROKER_PORT), timeout=5)
    except (OSError, asyncio.TimeoutError):
        log.error(f"无法连接MQTT Broker {BROKER_HOST}:{BROKER_PORT}")
        log.info("请先启动: python mqtt_broker.py")
        return

    if not await connect_mqtt(reader, writer):
        log.error("CONNACK失败")
        return
    log.info("已连接MQTT Broker")

    # 发送在线状态
    status = json.dumps({"status": "online", "timestamp": time.strftime("%H:%M:%S")})
    writer.write(build_publish("keweibo/v1/status", status.encode()))
    await writer.drain()

    while True:
        for i in range(1, FERMENTERS + 1):
            # 模拟正常波动 + 偶尔异常
            temp = 36.5 + random.gauss(0, 0.3)
            if random.random() < 0.02: temp += 3  # 2%概率温度异常
            ph = 6.8 + random.gauss(0, 0.1)
            do_val = 80 + random.gauss(0, 3)  # 溶氧
            level = 65 + random.gauss(0, 2)

            data = {
                "timestamp": time.strftime("%H:%M:%S"),
                "temperature": round(temp, 1),
                "ph": round(ph, 2),
                "do": round(do_val, 1),
                "level": round(level, 1),
                "pressure": round(0.05 + random.gauss(0, 0.003), 3)
            }
            topic = f"keweibo/v1/fermenter/{i}/data"
            writer.write(build_publish(topic, json.dumps(data).encode()))
            log.info(f"罐{i}: {data['temperature']}°C pH={data['ph']}")
        await writer.drain()
        await asyncio.sleep(INTERVAL)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("模拟器已停止")
