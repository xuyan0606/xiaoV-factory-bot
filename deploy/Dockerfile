# =============================================================================
# xiaoV Factory数字化项目 — Flask 服务端 Docker 镜像
# 基于 python:3.11-slim，轻量安全
# =============================================================================
FROM python:3.11-slim

LABEL maintainer="xiaoV Team <dev@xiaov.io>"
LABEL description="xiaoV Factory Bot Flask 服务端"
LABEL version="2.0"

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    FLASK_ENV=production \
    PORT=5001

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY deploy/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 5001

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# 启动命令：使用 gunicorn 生产级 WSGI 服务器
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "factory_bot_server:app"]
