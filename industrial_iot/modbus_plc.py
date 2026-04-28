#!/usr/bin/env python3
"""
科为博工业物联网 — Modbus TCP 模拟PLC
模拟PLC保持寄存器，供数据采集网关读取
"""
import asyncio, struct, random, time, logging

logging.basicConfig(level=logging.INFO, format='[PLC] %(message)s')
log = logging.getLogger('PLC')

PLC_HOST = '0.0.0.0'
PLC_PORT = 502

class ModbusPLC:
    """模拟PLC — 保持寄存器存储传感器数据"""
    def __init__(self):
        # 寄存器映射: float32需要2个寄存器
        self.registers = [0] * 100
        self.update_sensors()

    def update_sensors(self):
        """更新模拟传感器值到寄存器"""
        def to_regs(val):
            """float32 -> 2个uint16寄存器"""
            packed = struct.pack('>f', val)
            return list(struct.unpack('>HH', packed))

        # 地址0x0000-0x0003: 温度 (float32)
        temp = 36.5 + random.gauss(0, 0.3)
        self.registers[0:2] = to_regs(temp)
        # 0x0004-0x0007: pH
        ph = 6.8 + random.gauss(0, 0.1)
        self.registers[4:6] = to_regs(ph)
        # 0x0008-0x000B: 液位
        level = 65 + random.gauss(0, 2)
        self.registers[8:10] = to_regs(level)
        # 0x000C-0x000F: 压力
        pressure = 0.05 + random.gauss(0, 0.003)
        self.registers[12:14] = to_regs(pressure)
        # 0x0010: 设备状态 (1=运行, 0=停止)
        self.registers[16] = 1
        # 0x0011: 报警标志
        self.registers[17] = 1 if temp > 39 else 0

    def read_holding_registers(self, address, count):
        """读保持寄存器 (功能码03)"""
        if address + count > len(self.registers):
            return None, "地址越界"
        return self.registers[address:address+count], None

    def write_single_register(self, address, value):
        """写单个寄存器 (功能码06) — 用于设置参数"""
        if address < len(self.registers):
            self.registers[address] = value
            return True
        return False

    def build_response(self, transaction_id, unit_id, function_code, data):
        """构建Modbus TCP响应报文"""
        length = 2 + 1 + len(data)  # 单元标识符+功能码+数据
        header = struct.pack('>HHHB', transaction_id, 0, length, unit_id)
        return header + bytes([function_code]) + data

    def build_error_response(self, transaction_id, unit_id, function_code, exception_code):
        header = struct.pack('>HHHB', transaction_id, 0, 3, unit_id)
        return header + bytes([function_code | 0x80, exception_code])

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        log.info(f"连接: {addr}")
        try:
            while True:
                data = await asyncio.wait_for(reader.read(260), timeout=30)
                if not data or len(data) < 8: break

                transaction_id = struct.unpack('>H', data[0:2])[0]
                protocol_id = struct.unpack('>H', data[2:4])[0]
                length = struct.unpack('>H', data[4:6])[0]
                unit_id = data[6]
                function_code = data[7]

                if function_code == 3:  # 读保持寄存器
                    address = struct.unpack('>H', data[8:10])[0]
                    count = struct.unpack('>H', data[10:12])[0]
                    self.update_sensors()
                    regs, err = self.read_holding_registers(address, count)
                    if err:
                        resp = self.build_error_response(transaction_id, unit_id, function_code, 2)
                    else:
                        data_bytes = b''
                        for r in regs:
                            data_bytes += struct.pack('>H', r & 0xFFFF)
                        resp = self.build_response(transaction_id, unit_id, function_code,
                                                   bytes([len(data_bytes)]) + data_bytes)

                elif function_code == 6:  # 写单个寄存器
                    address = struct.unpack('>H', data[8:10])[0]
                    value = struct.unpack('>H', data[10:12])[0]
                    self.write_single_register(address, value)
                    resp = data[:8] + data[7:12]  # echo请求

                else:
                    resp = self.build_error_response(transaction_id, unit_id, function_code, 1)

                writer.write(resp)
                await writer.drain()

        except (asyncio.TimeoutError, ConnectionResetError):
            pass
        finally:
            log.info(f"断开: {addr}")
            try: writer.close()
            except: pass

    async def start(self):
        server = await asyncio.start_server(self.handle_client, PLC_HOST, PLC_PORT)
        log.info(f"Modbus PLC 启动: {PLC_HOST}:{PLC_PORT}")
        async with server:
            await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(ModbusPLC().start())
    except KeyboardInterrupt:
        log.info("PLC 已停止")
