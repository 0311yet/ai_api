# Dockerfile — 单阶段构建，前端 dist 已在本地构建好
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt uvicorn[standard]

# 复制后端代码
COPY backend/app ./app

# 复制已构建的前端静态文件
COPY frontend/dist ./static

# 数据持久化目录
RUN mkdir -p /app/data
ENV STATIC_DIR=/app/static
ENV DATABASE_URL=sqlite+aiosqlite:////app/data/ai_gateway.db

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
