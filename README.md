# 科为博工厂机器人 (CRVAB Factory Bot)

内蒙古科为博生物科技有限公司数字化工厂项目。

## 功能

- **钉钉群机器人** — 通过 incoming webhook 推送生产日报、设备告警
- **网页查询助手** (`/chat`) — 在浏览器中查询车间、设备、批次、配方等信息
- **虚拟工厂组织架构** (`/factory/org`) — 25个岗位角色对话系统，模拟车间主任、技术总监等岗位

## 快速启动

```bash
python3 factory_bot_server.py
```

服务运行在 http://localhost:5001

## 部署

使用 ngrok 暴露本地服务：
```bash
ngrok http 5001
```

在钉钉群中添加自定义机器人，配置 webhook 地址。
