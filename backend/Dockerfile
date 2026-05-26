FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据库目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 8082

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV DEBUG=false
ENV DATABASE_URL=sqlite+aiosqlite:///./data/k8s_dashboard.db

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8082/ || exit 1

# 单 worker：APScheduler 定时任务勿使用 --workers > 1 或多副本部署
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]
