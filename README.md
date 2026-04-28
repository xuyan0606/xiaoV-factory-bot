# xiaoV Factory Bot

AI 驱动的数字化工厂助手。

## 功能

- **钉钉群机器人** — 通过 incoming webhook 推送生产日报、设备告警
- **网页查询助手** (`/chat`) — 在浏览器中查询车间、设备、批次、配方等信息
- **虚拟工厂组织架构** (`/factory/org`) — 25个岗位角色对话系统，模拟车间主任、技术总监等岗位
- **MES 数据库** — 发酵行业核心业务表设计（批号追踪、工艺参数、质检、设备维保）
- **分布式监控** — 工业 IoT 数据采集、异常检测、熔断器、高可用消息队列
- **Docker 部署** — Flask + MQTT + Prometheus + Grafana 全套容器化

## 快速启动

```bash
python3 factory_bot_server.py
```

服务运行在 http://localhost:5001

## 部署

```bash
ngrok http 5001
```

在钉钉群中添加自定义机器人，配置 webhook 地址。
