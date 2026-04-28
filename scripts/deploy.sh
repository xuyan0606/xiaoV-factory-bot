#!/usr/bin/env bash
# =============================================================================
# 科为博工厂数字化项目 — 一键部署脚本
# 用法: bash scripts/deploy.sh [环境]
#   环境: production (默认) | staging
# =============================================================================
set -euo pipefail

# ==================== 配置 ====================
PROJECT_DIR="/Users/xuyan/software/hermesWorkspace"
DEPLOY_DIR="${PROJECT_DIR}/deploy"
COMPOSE_FILE="${DEPLOY_DIR}/docker-compose.yml"
ENV_FILE="${DEPLOY_DIR}/.env"
BACKUP_DIR="${PROJECT_DIR}/backups/$(date +%Y%m%d_%H%M%S)"
ROLLBACK_DIR="${PROJECT_DIR}/backups"
DOCKER_REGISTRY="ghcr.io"
IMAGE_NAME="crvab-factory-bot"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==================== 环境选择 ====================
ENV="${1:-production}"
echo -e "${BLUE}🔧 科为博工厂 — 部署脚本${NC}"
echo -e "${BLUE}================================${NC}"
echo -e "环境: ${YELLOW}${ENV}${NC}"
echo -e "项目目录: ${PROJECT_DIR}"
echo ""

# ==================== 前置检查 ====================
preflight_check() {
    echo -e "${BLUE}[1/7] 前置检查...${NC}"

    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ 未找到 Docker，请先安装 Docker${NC}"
        echo "   curl -fsSL https://get.docker.com | sh"
        exit 1
    fi
    echo -e "  ✅ Docker: $(docker --version)"

    # 检查 Docker Compose
    if ! command -v docker compose &> /dev/null; then
        echo -e "${RED}❌ 未找到 Docker Compose${NC}"
        exit 1
    fi
    echo -e "  ✅ Docker Compose: $(docker compose version)"

    # 检查 .env 文件
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}  ⚠️  未找到 .env 文件，从模板创建${NC}"
        cp "${DEPLOY_DIR}/.env.example" "$ENV_FILE"
        echo -e "  ✅ 已创建 ${ENV_FILE}"
        echo -e "  ${RED}⚠️  请编辑 ${ENV_FILE} 填入真实配置后重新运行${NC}"
        exit 1
    fi
    echo -e "  ✅ .env 文件就绪"

    # 检查必需目录
    for dir in "${DEPLOY_DIR}/prometheus" "${DEPLOY_DIR}/grafana/dashboards" "${DEPLOY_DIR}/mosquitto"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            echo -e "  📁 创建目录: $dir"
        fi
    done
    echo -e "  ✅ 目录结构就绪"

    echo ""
}

# ==================== 拉取最新代码 ====================
pull_latest_code() {
    echo -e "${BLUE}[2/7] 拉取最新代码...${NC}"

    # 保存当前版本的 Git 哈希
    OLD_VERSION=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")

    git -C "$PROJECT_DIR" fetch origin
    git -C "$PROJECT_DIR" reset --hard origin/main

    NEW_VERSION=$(git -C "$PROJECT_DIR" rev-parse HEAD)
    echo -e "  ✅ 代码已更新: ${OLD_VERSION:0:8} → ${NEW_VERSION:0:8}"
    echo ""
}

# ==================== 备份当前状态 ====================
backup_current() {
    echo -e "${BLUE}[3/7] 备份当前部署...${NC}"

    mkdir -p "$BACKUP_DIR"

    # 备份 docker-compose 配置
    if [ -f "$COMPOSE_FILE" ]; then
        cp "$COMPOSE_FILE" "${BACKUP_DIR}/docker-compose.yml"
    fi

    # 备份 .env
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "${BACKUP_DIR}/.env"
    fi

    # 备份 nginx 配置
    if [ -f "${DEPLOY_DIR}/nginx.conf" ]; then
        cp "${DEPLOY_DIR}/nginx.conf" "${BACKUP_DIR}/nginx.conf"
    fi

    # 备份 Prometheus 配置
    if [ -f "${DEPLOY_DIR}/prometheus/prometheus.yml" ]; then
        cp "${DEPLOY_DIR}/prometheus/prometheus.yml" "${BACKUP_DIR}/prometheus.yml"
    fi

    echo -e "  ✅ 已备份到: ${BACKUP_DIR}"

    # 清理旧备份（保留最近5个）
    BACKUP_COUNT=$(ls -d ${ROLLBACK_DIR}/2* 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt 5 ]; then
        ls -dt ${ROLLBACK_DIR}/2* | tail -n +6 | xargs rm -rf
        echo -e "  🧹 已清理旧备份（保留最近5个）"
    fi

    echo ""
}

# ==================== 构建 Docker 镜像 ====================
build_images() {
    echo -e "${BLUE}[4/7] 构建 Docker 镜像...${NC}"

    # 加载 .env
    set -a
    source "$ENV_FILE"
    set +a

    # 构建 Flask 应用镜像
    echo -e "  📦 构建 Flask 应用..."
    docker build -t "${IMAGE_NAME}:latest" \
        -f "${DEPLOY_DIR}/Dockerfile" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        "$PROJECT_DIR"

    # 打时间戳标签
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    docker tag "${IMAGE_NAME}:latest" "${IMAGE_NAME}:${TIMESTAMP}"
    echo -e "  ✅ 镜像构建完成: ${IMAGE_NAME}:${TIMESTAMP}"
    echo ""
}

# ==================== 拉取外部镜像 ====================
pull_external_images() {
    echo -e "${BLUE}[5/7] 拉取外部服务镜像...${NC}"

    # 并行拉取
    docker pull eclipse-mosquitto:2.0 &
    docker pull prom/prometheus:v2.53.0 &
    docker pull grafana/grafana:11.0.0 &
    docker pull prom/node-exporter:v1.8.0 &
    docker pull nginx:1.26-alpine &

    wait
    echo -e "  ✅ 所有外部镜像已更新"
    echo ""
}

# ==================== 启动/重启服务 ====================
start_services() {
    echo -e "${BLUE}[6/7] 启动服务...${NC}"

    # 加载 .env
    set -a
    source "$ENV_FILE"
    set +a

    cd "$PROJECT_DIR"

    # 停止旧服务（保留数据卷）
    echo -e "  🛑 停止旧服务..."
    docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
    sleep 2

    # 启动新服务
    echo -e "  🚀 启动新服务..."
    docker compose -f "$COMPOSE_FILE" up -d

    echo ""
}

# ==================== 健康检查 ====================
health_check() {
    echo -e "${BLUE}[7/7] 健康检查...${NC}"

    local MAX_RETRIES=12
    local RETRY_INTERVAL=5
    local retries=0

    # 检查 Flask 服务
    echo -e "  🔍 检查 Flask 服务..."
    while [ $retries -lt $MAX_RETRIES ]; do
        if curl -sf http://localhost:5001/health > /dev/null 2>&1; then
            echo -e "  ✅ Flask 服务正常 (http://localhost:5001/health)"
            break
        fi
        retries=$((retries + 1))
        if [ $retries -ge $MAX_RETRIES ]; then
            echo -e "  ${RED}❌ Flask 服务健康检查失败${NC}"
            echo -e "  ${YELLOW}  查看日志: docker compose logs flask-app${NC}"
            # 自动回滚
            rollback
            return 1
        fi
        sleep $RETRY_INTERVAL
    done

    # 检查 Prometheus
    if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo -e "  ✅ Prometheus 正常 (http://localhost:9090)"
    else
        echo -e "  ${YELLOW}  ⚠️  Prometheus 未就绪${NC}"
    fi

    # 检查 Grafana
    if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
        echo -e "  ✅ Grafana 正常 (http://localhost:3000)"
    else
        echo -e "  ${YELLOW}  ⚠️  Grafana 未就绪${NC}"
    fi

    # 检查 MQTT Broker
    if docker exec crvab-mqtt-broker mosquitto_sub -t '$SYS/broker/uptime' -C 1 -W 3 > /dev/null 2>&1; then
        echo -e "  ✅ MQTT Broker 正常 (port 1883)"
    else
        echo -e "  ${YELLOW}  ⚠️  MQTT Broker 未就绪${NC}"
    fi

    echo ""
}

# ==================== 回滚逻辑 ====================
rollback() {
    echo -e "\n${RED}⚠️  执行回滚...${NC}"

    # 找到最近的备份
    LATEST_BACKUP=$(ls -dt ${ROLLBACK_DIR}/2* 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        echo -e "${RED}❌ 未找到可用备份，回滚失败${NC}"
        exit 1
    fi

    echo -e "  恢复备份: ${LATEST_BACKUP}"

    # 恢复配置
    if [ -f "${LATEST_BACKUP}/docker-compose.yml" ]; then
        cp "${LATEST_BACKUP}/docker-compose.yml" "$COMPOSE_FILE"
    fi
    if [ -f "${LATEST_BACKUP}/.env" ]; then
        cp "${LATEST_BACKUP}/.env" "$ENV_FILE"
    fi

    # 回退 Git 版本
    echo -e "  🔄 回退 Git 版本..."
    git -C "$PROJECT_DIR" checkout HEAD~1 || true

    # 重启旧版本
    cd "$PROJECT_DIR"
    docker compose -f "$COMPOSE_FILE" up -d --force-recreate

    echo -e "${GREEN}✅ 回滚完成${NC}"
    exit 1
}

# ==================== 显示部署摘要 ====================
show_summary() {
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}✅ 科为博工厂部署完成！${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo -e "  📍 服务地址:"
    echo -e "     Flask 应用:   http://localhost:5001"
    echo -e "     Nginx 反向代理: http://localhost:80"
    echo -e "     Prometheus:    http://localhost:9090"
    echo -e "     Grafana:       http://localhost:3000 (admin/admin)"
    echo -e "     MQTT Broker:  tcp://localhost:1883"
    echo -e "     MQTT WS:      ws://localhost:9001"
    echo ""
    echo -e "  📊 监控端点:"
    echo -e "     应用指标:     http://localhost:5001/metrics"
    echo -e "     健康检查:     http://localhost:5001/health"
    echo -e "     主机指标:     http://localhost:9100/metrics"
    echo ""
    echo -e "  📋 常用命令:"
    echo -e "     查看日志:     docker compose logs -f [service]"
    echo -e "     重启服务:     docker compose restart [service]"
    echo -e "     停止所有:     docker compose down"
    echo -e "     重新构建:     docker compose build"
    echo ""
    echo -e "  💾 备份位置: ${BACKUP_DIR}"
    echo ""
}

# ==================== 主流程 ====================
main() {
    echo -e "${BLUE}🚀 科为博工厂 — ${ENV}部署开始${NC}"
    echo -e "${BLUE}================================${NC}"

    preflight_check
    pull_latest_code
    backup_current
    build_images
    pull_external_images
    start_services
    health_check
    show_summary

    echo -e "${GREEN}🎉 部署成功！${NC}"
}

# 捕获错误
trap 'echo -e "${RED}❌ 部署脚本执行失败${NC}"; exit 1' ERR

# 执行主流程
main
