# frontend.Dockerfile — 构建前端静态文件
FROM node:22-alpine AS frontend-build

WORKDIR /build
RUN corepack enable && corepack prepare pnpm@10.29.3 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# 输出 dist/ 到 /build/dist
