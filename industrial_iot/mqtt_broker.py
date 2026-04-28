#!/usr/bin/env python3
"""
科为博工业物联网 — MQTT 轻量级 Broker
纯Python实现，基于asyncio，零依赖。
"""
import asyncio, struct, time, json, logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='[MQTT] %(message)s')
log = logging.getLogger('MQTT')

# ==================== MQTT 协议常量 ====================
CONNECT, CONNACK, PUBLISH, PUBACK, SUBSCRIBE, SUBACK, UNSUBSCRIBE, UNSUBACK, PINGREQ, PINGRESP, DISCONNECT = range(1, 12)

class MQTTSession:
    """单个客户端连接会话"""
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.address = writer.get_extra_info('peername')
        self.client_id = ''
        self.clean_session = True
        self.keepalive = 0
        self.last_active = time.time()
        self.subscriptions = {}  # {topic_filter: qos}
        self.will_topic = None
        self.will_message = None
        self.will_qos = 0
        self.active = True

    async def send(self, packet_type, data=b''):
        """发送MQTT报文"""
        remaining = len(data)
        header = bytes([(packet_type << 4)])
        while remaining > 0:
            enc = remaining % 128
            remaining //= 128
            if remaining > 0: enc |= 128
            header += bytes([enc])
        self.writer.write(header + data)
        await self.writer.drain()

    async def send_connack(self, session_present=False, return_code=0):
        await self.send(CONNACK, bytes([session_present, return_code]))

    async def send_suback(self, packet_id, qos_list):
        data = struct.pack('>H', packet_id) + bytes(qos_list)
        await self.send(SUBACK, data)

    async def send_publish(self, topic, payload, qos=0):
        topic_enc = topic.encode()
        data = struct.pack('>H', len(topic_enc)) + topic_enc + (payload if isinstance(payload, bytes) else payload.encode())
        await self.send(PUBLISH, data)


class MQTTServer:
    """MQTT Broker 核心"""
    def __init__(self, host='0.0.0.0', port=1883):
        self.host, self.port = host, port
        self.sessions = {}
        self.subscriptions = defaultdict(list)  # topic_filter -> [(session, qos)]

    def decode_remaining_length(self, data):
        """解码剩余长度（变长编码）"""
        value, multiplier, idx = 0, 1, 0
        while True:
            byte = data[idx]; idx += 1
            value += (byte & 127) * multiplier
            multiplier *= 128
            if not (byte & 128): break
        return value, idx

    def match_topic(self, filter_str, topic):
        """MQTT主题匹配，支持+和#通配符"""
        filt = filter_str.split('/')
        top = topic.split('/')
        for i, f in enumerate(filt):
            if f == '#': return True
            if i >= len(top): return False
            if f != '+' and f != top[i]: return False
        return len(filt) == len(top)

    def deliver_publish(self, topic, payload, qos=0):
        """推送消息到所有匹配的订阅者"""
        for filter_str, subs in list(self.subscriptions.items()):
            if self.match_topic(filter_str, topic):
                for session, sub_qos in subs:
                    if session.active:
                        asyncio.create_task(session.send_publish(topic, payload, min(qos, sub_qos)))

    async def process_packet(self, session, packet_type, data):
        """处理MQTT报文"""
        if packet_type == CONNECT:
            idx = 0
            # Protocol Name (2 bytes length + UTF-8 string)
            proto_len = struct.unpack('>H', data[idx:idx+2])[0]; idx += 2
            proto_name = data[idx:idx+proto_len].decode(); idx += proto_len
            proto_level = data[idx]; idx += 1
            flags = data[idx]; idx += 1
            session.keepalive = struct.unpack('>H', data[idx:idx+2])[0]; idx += 2
            # Client ID
            cl_len = struct.unpack('>H', data[idx:idx+2])[0]; idx += 2
            session.client_id = data[idx:idx+cl_len].decode(); idx += cl_len
            session.clean_session = bool(flags & 0x02)
            session.will_flag = bool(flags & 0x04)
            session.will_qos = (flags & 0x18) >> 3
            # Will Topic / Message
            if session.will_flag:
                wt_len = struct.unpack('>H', data[idx:idx+2])[0]; idx += 2
                session.will_topic = data[idx:idx+wt_len].decode(); idx += wt_len
                wm_len = struct.unpack('>H', data[idx:idx+2])[0]; idx += 2
                session.will_message = data[idx:idx+wm_len].decode()
            # 保存会话
            self.sessions[session.client_id] = session
            await session.send_connack()
            log.info(f"连接: {session.client_id}")

        elif packet_type == SUBSCRIBE:
            idx = 2
            packet_id = struct.unpack('>H', data[0:2])[0]
            qos_list = []
            while idx < len(data):
                tlen = struct.unpack('>H', data[idx:idx+2])[0]; idx += 2
                topic = data[idx:idx+tlen].decode(); idx += tlen
                qos = data[idx]; idx += 1
                qos_list.append(qos)
                session.subscriptions[topic] = qos
                self.subscriptions[topic].append((session, qos))
                log.info(f"订阅: {session.client_id} -> {topic}")
            await session.send_suback(packet_id, qos_list)

        elif packet_type == PUBLISH:
            idx = 0
            flags = packet_type  # 已在函数参数传入
            dup = (data[0] & 0x08) >> 3
            qos = (data[0] & 0x06) >> 1
            retain = data[0] & 0x01
            remaining, _ = self.decode_remaining_length(data[1:])
            data = data[1:]  # 跳过剩余长度
            idx = 0 if qos == 0 else 2
            tlen = struct.unpack('>H', data[idx:idx+2])[0]; idx += 2
            topic = data[idx:idx+tlen].decode(); idx += tlen
            payload = data[idx:]
            log.info(f"发布: {topic} <- {session.client_id}")
            session.last_active = time.time()
            self.deliver_publish(topic, payload, qos)
            # 保存遗嘱消息
            if session.will_topic:
                session.will_topic = topic
                session.will_message = payload

        elif packet_type == PINGREQ:
            await session.send(PINGRESP)
            session.last_active = time.time()

        elif packet_type == DISCONNECT:
            session.active = False

    async def handle_client(self, reader, writer):
        """处理客户端连接"""
        session = MQTTSession(reader, writer)
        buffer = b''
        try:
            while True:
                data = await asyncio.wait_for(reader.read(4096), timeout=60)
                if not data: break
                buffer += data
                while len(buffer) >= 2:
                    packet_type = (buffer[0] >> 4)
                    remaining, used = self.decode_remaining_length(buffer[1:])
                    total = 1 + used + remaining
                    if len(buffer) < total: break
                    packet_data = buffer[1+used:total]
                    await self.process_packet(session, packet_type, packet_data)
                    buffer = buffer[total:]
        except (asyncio.TimeoutError, ConnectionResetError, OSError):
            pass
        finally:
            # 发布遗嘱消息
            if session.will_topic:
                log.warning(f"遗嘱: {session.client_id} 断开 -> {session.will_topic}")
                self.deliver_publish(session.will_topic, session.will_message, session.will_qos)
            session.active = False
            for topic, subs in list(self.subscriptions.items()):
                self.subscriptions[topic] = [(s, q) for s, q in subs if s != session]
            try:
                writer.close()
            except: pass

    async def start(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        log.info(f"MQTT Broker 启动: {self.host}:{self.port}")
        async with server:
            await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(MQTTServer().start())
    except KeyboardInterrupt:
        log.info("Broker 已停止")
