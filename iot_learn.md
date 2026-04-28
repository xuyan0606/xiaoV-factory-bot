# 工业物联网与时序数据库学习笔记

## MQTT协议
- 发布/订阅模式，Broker中转
- QoS 0/1/2：最多一次/至少一次/恰好一次
- 保留消息(Retain)：新订阅者立即可见最后一条
- 遗嘱消息(Last Will)：设备掉线通知
- 主题设计：`factory/line1/sensor/temperature`
- Python库：`paho-mqtt`

## Modbus协议
- RTU：串口RS-232/485，CRC校验
- TCP：以太网，端口502
- 寄存器：线圈(1bit)、离散输入(1bit只读)、输入寄存器(16bit只读)、保持寄存器(16bit读写)
- 功能码：03读保持寄存器、06写单个、16写多个
- Python库：`pymodbus`

## OPC UA（了解）
- 节点树形地址空间，Client/Server模式
- 标准化数据模型，安全通信
- Python库：`opcua-asyncua`

## TDengine时序数据库
- 超级表(Super Table)：列+标签(静态元数据)
- 窗口聚合：`INTERVAL(5m)`
- 适合设备传感器海量数据

## InfluxDB 2.x
- Bucket/Measurement/Tag/Field
- Flux查询语言，函数式
- Bucket设置保留策略自动过期
