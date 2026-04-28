# =============================================================================
# 科为博工厂数字化项目 — 一键部署文档
# 内蒙古科为博生物科技有限公司
# =============================================================================

# 科为博工厂数字化项目部署指南

## 项目概述

科为博工厂数字化项目是面向内蒙古科为博生物科技有限公司的智能制造升级项目，包含：

- **工厂机器人**（Flask）：钉钉群机器人，提供车间状态查询、生产批次追踪、设备管理等功能
- **工业IoT系统**：MQTT消息中间件、Modbus PLC模拟、数据采集网关、SCADA大屏
- **分布式系统**：一致性哈希设备分配、消息队列、熔断器容错、异常检测、RAG知识库
- **智能监控**：Prometheus + Grafana 全栈监控，含传感器趋势、系统状态、异常告警

---

## 环境要求

### 硬件要求

| 资源 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU  | 2 核    | 4 核    |
| 内存 | 4 GB    | 8 GB    |
| 磁盘 | 20 GB   | 50 GB SSD |
| 网络 | 100 Mbps | 1000 Mbps |

### 软件要求

- **操作系统**: Linux (Ubuntu 22.04+/CentOS 8+), macOS, Windows WSL2
- **Docker**: 24.0+
- **Docker Compose**: v2.20+ (推荐使用 `docker compose` 插件版)
- **Git**: 2.30+
- **Python**: 3.10+ (仅本地开发需要)

### 端口占用

| 端口 | 服务         | 说明                    |
|------|-------------|------------------------|
| 80   | Nginx       | HTTP 反向代理            |
| 443  | Nginx       | HTTPS (生产环境启用)      |
| 5001 | Flask 应用   | 工厂机器人 API           |
| 1883 | MQTT Broker | MQTT 协议端口            |
| 9001 | MQTT WS     | MQTT WebSocket 端口     |
| 9090 | Prometheus  | 监控系统                  |
| 3000 | Grafana     | 可视化面板                |
| 9100 | Node Exporter | 主机指标采集            |

---

## 快速开始

### 1. 克隆项目

```bash
cd /Users/xuyan/software/hermesWorkspace
```

### 2. 配置环境变量

```bash
cd deploy
cp .env.example .env
# 编辑 .env 文件，填入真实配置
vim .env
```

**必须修改的配置项：**

- `DINGTALK_TOKEN`: 钉钉机器人 Token（默认值仅供开发测试）
- `DINGTALK_WEBHOOK`: 钉钉群 Webhook 地址
- `GRAFANA_ADMIN_PASSWORD`: Grafana 管理员密码

### 3. 一键部署

**方式一：使用部署脚本（推荐）**

```bash
bash scripts/deploy.sh
```

**方式二：直接使用 Docker Compose**

```bash
cd deploy
docker compose up -d
```

### 4. 验证部署

```bash
# 检查所有服务状态
docker compose ps

# 查看运行日志
docker compose logs -f

# 验证 Flask 服务
curl http://localhost:5001/health

# 验证 Prometheus 指标
curl http://localhost:5001/metrics

# 查看 Prometheus 自身状态
curl http://localhost:9090/-/healthy
```

### 5. 访问服务

| 服务 | 地址 | 默认账号 |
|------|------|---------|
| Flask 应用 | http://localhost:5001 | — |
| Nginx 代理 | http://localhost:80 | — |
| 网页聊天 | http://localhost:5001/chat | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / admin |
| MQTT | tcp://localhost:1883 | — |
| MQTT WS | ws://localhost:9001 | — |

---

## 配置说明

### 环境变量 (.env)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FLASK_ENV` | 运行环境 | production |
| `DINGTALK_TOKEN` | 钉钉安全校验Token | crvab_factory_2026 |
| `DINGTALK_WEBHOOK` | 钉钉群Webhook | (必填) |
| `GRAFANA_ADMIN_USER` | Grafana管理员 | admin |
| `GRAFANA_ADMIN_PASSWORD` | Grafana密码 | admin |
| `PROMETHEUS_RETENTION` | 数据保留时间 | 15d |
| `TZ` | 时区 | Asia/Shanghai |

### Nginx 配置

Nginx 作为统一入口，代理所有内部服务：

- `/` — Flask 应用
- `/prometheus/` — Prometheus
- `/grafana/` — Grafana

生产环境建议：
1. 配置 SSL 证书（取消 nginx.conf 中 HTTPS 部分的注释）
2. 为 Prometheus 启用基本认证（取消 `auth_basic` 注释）
3. 使用 htpasswd 创建认证用户

### Prometheus 配置

抓取配置位于 `deploy/prometheus/prometheus.yml`，默认采集：

| 目标 | 端点 | 间隔 |
|------|------|------|
| Flask 应用 | flask-app:5001/metrics | 15s |
| MQTT Broker | mqtt-broker:1883/metrics | 30s |
| Node Exporter | node-exporter:9100 | 30s |
| Prometheus 自身 | localhost:9090 | 30s |

### Grafana 面板

面板配置位于 `deploy/grafana/dashboards/factory_overview.json`，包含：

1. **工厂运行状态** — 运行车间数、在产批次、MQTT连接数、异常告警数
2. **HTTP请求速率** — 各端点请求量趋势
3. **请求延迟** — P50/P95/P99 延迟分析
4. **传感器趋势** — 发酵温度等设备指标
5. **MQTT消息速率** — 消息通讯流量
6. **系统状态总览** — 所有服务健康状态表
7. **异常检测分布** — 各类异常占比饼图

---

## 生产部署建议

### 1. 安全性加固

```bash
# 为 Grafana 修改默认密码
# 登录 http://localhost:3000 → 配置 → 用户 → 修改密码

# 为 Prometheus 添加基本认证
htpasswd -c /etc/nginx/.htpasswd admin

# 为 MQTT 配置密码认证
# 编辑 deploy/mosquitto/mosquitto.conf，取消密码相关注释
mosquitto_passwd -c /mosquitto/config/passwd admin
```

### 2. HTTPS 配置

```bash
# 使用 Let's Encrypt 获取证书
docker run -it --rm -p 80:80 -p 443:443 \
  -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  -d factory.crvab.com
```

### 3. 数据持久化

Docker Compose 已配置命名卷持久化：

| 卷 | 挂载点 | 说明 |
|----|--------|------|
| `prometheus-data` | /prometheus | Prometheus TSDB 数据 |
| `grafana-data` | /var/lib/grafana | Grafana 配置+面板 |
| `mosquitto-data` | /mosquitto/data | MQTT 持久化消息 |
| `iot-data` | /data | 工厂IoT数据库 |

### 4. 资源限制

生产环境建议在 docker-compose.yml 中添加资源限制：

```yaml
services:
  flask-app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 5. 日志管理

默认日志配置：
- 驱动：json-file
- 最大大小：10MB/文件
- 保留：3个文件

生产环境建议使用 ELK/Loki 集中式日志方案。

### 6. 备份策略

```bash
# 使用部署脚本自动备份
# 每次部署自动创建备份到 backups/ 目录，保留最近5份

# 手动备份
tar czf backup-$(date +%Y%m%d).tar.gz \
  iot_data.db \
  distributed/knowledge_base.db \
  deploy/.env \
  deploy/prometheus/ \
  deploy/grafana/
```

---

## 服务管理与操作

### 启动/停止

```bash
# 启动所有服务
cd deploy && docker compose up -d

# 停止所有服务
docker compose down

# 重启单个服务
docker compose restart flask-app

# 查看服务日志
docker compose logs -f flask-app
```

### 更新部署

```bash
# 方式一：使用部署脚本（自动备份+回滚）
bash scripts/deploy.sh

# 方式二：手动更新
git pull origin main
docker compose -f deploy/docker-compose.yml build flask-app
docker compose -f deploy/docker-compose.yml up -d
```

### 回滚

```bash
# 使用部署脚本的自动回滚
# 当健康检查失败时自动执行，或手动触发：

# 找到最近的备份
ls -lt backups/

# 恢复配置并重启
cp backups/20260427_183000/docker-compose.yml deploy/
docker compose -f deploy/docker-compose.yml up -d
```

---

## 健康检查与故障排查

### 健康检查端点

| 端点 | 服务 | 预期响应 |
|------|------|---------|
| `/health` | Flask | `{"status":"ok","factory":"内蒙古科为博生物科技","version":"2.0"}` |
| `/-/healthy` | Prometheus | 空响应 200 OK |
| `/api/health` | Grafana | `{"database":"ok",...}` |
| `$SYS/broker/uptime` | MQTT | uptime 数值 |
| `/nginx-health` | Nginx | "healthy\n" |

### 常见问题

#### Q: Flask 服务启动失败

```bash
# 查看详细日志
docker compose logs flask-app

# 检查端口占用
lsof -i :5001

# 检查 Python 依赖
docker exec crvab-flask-app pip list
```

#### Q: MQTT 连接失败

```bash
# 验证 Broker 运行状态
docker exec crvab-mqtt-broker mosquitto_sub -t '$SYS/#' -C 1

# 检查端口
nc -zv localhost 1883

# 查看 Mosquitto 日志
docker compose logs mqtt-broker
```

#### Q: Prometheus 抓取不到指标

```bash
# 检查 target 状态
# 访问 http://localhost:9090/targets

# 验证 metrics 端点
curl http://localhost:5001/metrics

# 测试容器间通信
docker exec crvab-prometheus wget -qO- http://flask-app:5001/metrics
```

#### Q: Grafana 面板不显示数据

```bash
# 检查数据源配置
# 访问 http://localhost:3000/datasources

# 验证 Prometheus 数据源连通性
# 进入 Grafana → 配置 → Data Sources → Prometheus → Test

# 检查 Prometheus 是否有数据
# http://localhost:9090/graph → 输入 `up` → Execute
```

#### Q: Docker 资源不足

```bash
# 查看资源使用
docker stats

# 清理无用的镜像和卷
docker system prune -af

# 增加 Docker 磁盘空间（macOS Docker Desktop）
# Preferences → Resources → Disk image size
```

#### Q: 部署脚本报错

```bash
# 检查 .env 配置是否正确
cat deploy/.env

# 手动执行步骤排查
docker compose -f deploy/docker-compose.yml config

# 跳过 Git 操作手动部署
bash scripts/deploy.sh --no-git-pull
```

---

## 架构图

```
                      ┌─────────────────────┐
                      │     Nginx :80/443    │
                      │   反向代理 + SSL     │
                      └──────────┬──────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
     ┌────────▼──────┐  ┌───────▼───────┐  ┌───────▼───────┐
     │  Flask 应用   │  │  Prometheus   │  │   Grafana     │
     │  :5001        │  │  :9090        │  │  :3000        │
     │  工厂机器人   │  │  指标采集     │  │  可视化面板   │
     └───────┬───────┘  └───────────────┘  └───────────────┘
             │
     ┌───────▼───────┐
     │  MQTT Broker  │
     │  :1883        │
     │  Eclipse Mosq │
     └───────┬───────┘
             │
     ┌───────▼───────┐
     │  Node Exporter│
     │  :9100        │
     │  主机监控     │
     └───────────────┘
```

---

## 项目结构

```
hermesWorkspace/
├── factory_bot_server.py          # Flask 工厂机器人主服务
├── factory_managers.py            # 车间主任模块
├── monitoring/
│   └── metrics.py                 # Prometheus 指标采集
├── industrial_iot/
│   ├── mqtt_broker.py             # MQTT Broker 实现
│   ├── modbus_plc.py              # Modbus PLC 模拟
│   ├── data_gateway.py            # 数据采集网关
│   └── scada_dashboard.html       # SCADA 大屏
├── distributed/
│   ├── test_distributed.py        # 分布式系统集成测试
│   ├── circuit_breaker.py         # 熔断器
│   ├── collector_engine.py        # 一致性哈希采集引擎
│   ├── ha_queue.py                # 高可用消息队列
│   ├── distributed_store.py       # 分布式存储
│   ├── monitor.py                 # 分布式监控
│   ├── smart_monitor.py           # 智能监控中心
│   └── rag_knowledge_base.py      # RAG 知识库
├── deploy/
│   ├── docker-compose.yml         # Docker 编排
│   ├── Dockerfile                 # Flask 应用镜像
│   ├── requirements.txt           # Python 依赖
│   ├── nginx.conf                 # Nginx 反向代理
│   ├── .env.example               # 环境变量模板
│   ├── prometheus/
│   │   └── prometheus.yml         # Prometheus 配置
│   ├── grafana/
│   │   ├── datasources/           # 数据源自动配置
│   │   └── dashboards/            # 面板定义
│   ├── mosquitto/
│   │   └── mosquitto.conf         # MQTT Broker 配置
│   └── README.md                  # 本文件
├── scripts/
│   └── deploy.sh                  # 一键部署脚本
└── .github/workflows/
    └── deploy.yml                 # GitHub Actions CI/CD
```

---

## 许可证

Copyright (c) 2026 内蒙古科为博生物科技有限公司

---

*文档版本: v2.0 | 最后更新: 2026-04-27*
