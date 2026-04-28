#!/usr/bin/env python3
"""
xiaoV工业物联网 — 数据采集网关
统一采集MQTT/Modbus/OPC UA数据，存入SQLite，推送WebSocket
"""
import asyncio, json, sqlite3, time, struct, logging, os, threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket, struct as sock_struct

logging.basicConfig(level=logging.INFO, format='[GATEWAY] %(message)s')
log = logging.getLogger('GATEWAY')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history.db')
WS_PORT = 8765
HTTP_PORT = 8080

# ==================== 数据库 ====================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT, device TEXT, metric TEXT,
        value REAL, unit TEXT, timestamp TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device TEXT, message TEXT, level TEXT, timestamp TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ts ON measurements(timestamp)")
    conn.commit()
    conn.close()
    log.info(f"数据库: {DB_PATH}")

def store_measurement(source, device, metric, value, unit=''):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO measurements VALUES (NULL,?,?,?,?,?,datetime('now','localtime'))",
                 (source, device, metric, value, unit))
    conn.commit()
    conn.close()

def store_alarm(device, message, level='WARN'):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO alarms VALUES (NULL,?,?,?,datetime('now','localtime'))",
                 (device, message, level))
    conn.commit()
    conn.close()
    log.warning(f"⚠️ 告警: {device} - {message}")

# ==================== WebSocket Server ====================
ws_clients = set()

async def ws_handler(reader, writer):
    """处理WebSocket连接"""
    ws_clients.add(writer)
    addr = writer.get_extra_info('peername')
    log.info(f"WS连接: {addr}")
    try:
        # WebSocket握手
        data = await reader.read(4096)
        if b'Upgrade' in data and b'websocket' in data:
            # 提取Sec-WebSocket-Key
            for line in data.decode().split('\r\n'):
                if 'Sec-WebSocket-Key' in line:
                    key = line.split(': ')[1].strip()
                    import hashlib, base64
                    accept = base64.b64encode(hashlib.sha1(
                        (key + '258EAFA5-E914-47DA-95CA-5AB5E9741B6F').encode()).digest()).decode()
                    resp = (f"HTTP/1.1 101 Switching Protocols\r\n"
                            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                            f"Sec-WebSocket-Accept: {accept}\r\n\r\n")
                    writer.write(resp.encode())
                    await writer.drain()
                    # 保持连接，等待关闭
                    try:
                        while True:
                            data = await asyncio.wait_for(reader.read(4096), timeout=60)
                            if not data: break
                    except: pass
                    break
    except: pass
    finally:
        ws_clients.discard(writer)
        try: writer.close()
        except: pass

async def ws_broadcast(data):
    """广播给所有WebSocket客户端"""
    msg = json.dumps(data).encode()
    frame = bytes([0x81, len(msg)]) + msg
    for w in list(ws_clients):
        try:
            w.write(frame)
            await w.drain()
        except:
            ws_clients.discard(w)

# ==================== MQTT 采集 ====================
async def collect_mqtt():
    """订阅MQTT数据"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection('127.0.0.1', 1883), timeout=3)
    except:
        log.warning("MQTT Broker不可用")
        return

    # CONNECT
    cid = 'gateway_' + str(int(time.time()))
    connect_pkt = (b'\x10' + bytes([17 + len(cid)]) +
                   b'\x00\x04MQTT\x04\x02\x00\x3c' +
                   struct.pack('>H', len(cid)) + cid.encode())
    writer.write(connect_pkt); await writer.drain()
    await reader.read(4)

    # SUBSCRIBE to keweibo/v1/fermenter/+/data
    topic = b'keweibo/v1/fermenter/+/data'
    sub_pkt = (b'\x82' + bytes([5 + len(topic)]) +
               b'\x00\x01' + struct.pack('>H', len(topic)) + topic + b'\x00')
    writer.write(sub_pkt); await writer.drain()
    await reader.read(5)
    log.info("MQTT 已订阅")

    while True:
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=30)
            if not data: break
            # 解析PUBLISH报文
            packet_type = data[0] >> 4
            if packet_type == 3:
                remaining = data[1] & 0x7F
                idx = 2
                tlen = struct.unpack('>H', data[idx:idx+2])[0]; idx += 2
                topic = data[idx:idx+tlen].decode(); idx += tlen
                payload = json.loads(data[idx:idx+remaining - (2+tlen)])
                # 提取设备ID
                parts = topic.split('/')
                device = f"fermenter_{parts[3]}" if len(parts) >= 4 else "unknown"
                for key in ['temperature', 'ph', 'do', 'level', 'pressure']:
                    if key in payload:
                        store_measurement('mqtt', device, key, payload[key])
                await ws_broadcast({"type":"mqtt","device":device,"data":payload})

                # 异常检测
                if payload.get('temperature', 0) > 39:
                    store_alarm(device, f"温度异常: {payload['temperature']}°C", 'CRITICAL')
                if payload.get('ph', 7) > 8.5 or payload.get('ph', 7) < 5.5:
                    store_alarm(device, f"pH异常: {payload['ph']}", 'WARN')
        except asyncio.TimeoutError:
            # 发PINGREQ保活
            writer.write(b'\xc0\x00'); await writer.drain()
        except: break

# ==================== Modbus 采集 ====================
async def collect_modbus():
    """轮询Modbus PLC"""
    await asyncio.sleep(2)
    while True:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection('127.0.0.1', 502), timeout=3)
            # 读保持寄存器（地址0，共18个寄存器）
            req = struct.pack('>HHHBBHH', 0x0001, 0, 6, 1, 3, 0, 18)
            writer.write(req); await writer.drain()
            resp = await asyncio.wait_for(reader.read(260), timeout=5)
            writer.close()

            if len(resp) >= 9:
                def to_float(regs):
                    return struct.unpack('>f', struct.pack('>HH', regs[0], regs[1]))[0]

                regs_data = resp[9:]
                regs = [struct.unpack('>H', regs_data[i:i+2])[0] for i in range(0, len(regs_data), 2)]

                data = {
                    "temperature": round(to_float(regs[0:2]), 1),
                    "ph": round(to_float(regs[4:6]), 2),
                    "level": round(to_float(regs[8:10]), 1),
                    "pressure": round(to_float(regs[12:14]), 3),
                    "status": regs[16],
                    "alarm": regs[17]
                }
                store_measurement('modbus', 'plc_01', 'temperature', data['temperature'])
                store_measurement('modbus', 'plc_01', 'ph', data['ph'])
                store_measurement('modbus', 'plc_01', 'level', data['level'])
                await ws_broadcast({"type":"modbus","device":"plc_01","data":data})

                if data['alarm']:
                    store_alarm('plc_01', f"PLC报警: T={data['temperature']}°C", 'CRITICAL')

        except (OSError, asyncio.TimeoutError):
            log.warning("Modbus PLC不可用")
        await asyncio.sleep(3)

# ==================== HTTP服务 ====================
class SCADAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    def log_message(self, format, *args):
        pass  # 静默日志

def start_http():
    server = HTTPServer(('0.0.0.0', HTTP_PORT), SCADAHandler)
    log.info(f"HTTP服务: http://127.0.0.1:{HTTP_PORT}/scada_dashboard.html")
    server.serve_forever()

# ==================== 主程序 ====================
async def main():
    init_db()
    # 启动HTTP
    threading.Thread(target=start_http, daemon=True).start()
    # 启动WebSocket
    ws_server = await asyncio.start_server(ws_handler, '0.0.0.0', WS_PORT)
    log.info(f"WebSocket: ws://127.0.0.1:{WS_PORT}")
    # 启动采集
    await asyncio.gather(
        collect_mqtt(),
        collect_modbus(),
        ws_server.serve_forever(),
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("网关已停止")
