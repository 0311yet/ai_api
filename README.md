# AI API Gateway

一个轻量级的 AI API 网关，支持多上游 Provider、模型池路由、客户端 Key 管理，同时兼容 OpenAI 和 Anthropic 两种 API 格式。前端 Vue 3 + Naive UI，后端 FastAPI + SQLite，单容器部署。

## 功能特性

- **多上游 Provider 管理**：配置多个 OpenAI 兼容上游，按需启停
- **模型池路由**：4 种策略
  - `priority` — 按优先级顺序，主路挂掉自动切备
  - `round_robin` — 轮询
  - `weighted` — 加权随机
  - `random` — 纯随机
- **客户端 Key 管理**：为每个客户端签发独立 Key，绑定到指定模型池，可限定允许的模型列表
- **双 API 格式兼容**：
  - `POST /v1/chat/completions` — OpenAI 格式（流式/非流式）
  - `POST /v1/messages` — Anthropic 格式（自动转换为 OpenAI 调用上游，再转回 Anthropic 响应）
  - `GET /v1/models`
- **请求日志与统计**：每次请求记录模型、状态、token、延迟、TTFT；Dashboard 实时展示总览
- **管理后台**：7 个页面（登录 / Dashboard / Providers / Pools / Keys / Logs / Stats），单密码登录

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + TypeScript + Pinia + Vue Router + Naive UI + Tailwind CSS + ECharts |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + httpx + Alembic |
| 数据库 | SQLite + WAL 模式 |
| 部署 | Docker + Docker Compose（单容器，静态文件由 FastAPI 挂载） |

## 目录结构

```
ai_api/
├── Dockerfile                  # 后端镜像构建
├── docker-compose.yml          # 生产部署编排
├── backend/
│   ├── .env                    # 本地配置（不入库）
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI 入口 + SPA 静态挂载
│       ├── config.py           # 环境变量配置
│       ├── database.py         # 异步 session
│       ├── middleware.py       # X-Admin-Key 鉴权
│       ├── schemas.py          # Pydantic 模型
│       ├── models/             # SQLAlchemy 表定义
│       ├── routers/
│       │   ├── auth.py         # 登录
│       │   ├── providers.py    # 上游管理
│       │   ├── pools.py        # 模型池管理
│       │   ├── keys.py         # 客户端 Key 管理
│       │   ├── logs.py         # 请求日志
│       │   ├── stats.py        # 统计聚合
│       │   └── proxy.py        # 代理 (OpenAI + Anthropic)
│       └── services/
│           ├── pool_router.py  # 4 种路由策略
│           └── proxy.py        # 流式/非流式代理核心
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── views/              # 7 个页面
        ├── components/
        ├── layouts/
        └── ...
```

## 数据模型

6 张表：

| 表 | 用途 |
|---|---|
| `providers` | 上游 API 配置（name、base_url、api_key、models） |
| `pools` | 模型池（name、display_name、strategy） |
| `pool_items` | 模型池成员（pool_id、provider_id、model、priority、weight） |
| `client_keys` | 客户端 Key（key、name、pool_id、allowed_models） |
| `request_logs` | 每次请求记录（model、status、tokens、latency、ttft） |
| `daily_stats` | 按日聚合的统计快照 |

## 快速开始

### 前置要求
- Docker + Docker Compose
- Node.js 22+ 和 pnpm（仅前端开发或重新构建时需要）

### 1. 克隆并构建前端
```bash
cd frontend
pnpm install
pnpm build      # 产物输出到 frontend/dist/
```

### 2. 配置
```bash
# 可选：修改 docker-compose.yml 中的 ADMIN_PASSWORD
# 默认 admin key 是 sk-admin-123456
```

### 3. 启动
```bash
docker compose up -d --build
```

服务启动后：
- 管理后台：http://localhost:8080
- API 文档：http://localhost:8080/docs
- 健康检查：http://localhost:8080/health

### 4. 后台配置流程
1. 浏览器打开 http://localhost:8080，输入 admin key 登录
2. 在 **Providers** 页添加上游 API（base_url 形如 `https://api.openai.com/v1`）
3. 在 **Pools** 页创建模型池，配置成员（选择 provider + 写 model 名 + 优先级/权重）
4. 在 **Keys** 页签发客户端 Key，绑定到模型池
5. 用客户端 Key 调用网关

## 客户端接入示例

### OpenAI 格式
```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <client-key>" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "hi"}],
    "stream": false
  }'
```

### Anthropic 格式（兼容 Claude 客户端、CC Switch 等）
```bash
curl http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <client-key>" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 1024,
    "stream": false
  }'
```

> **说明**：网关不会改写客户端发送的 `model` 字段，直接用它匹配模型池的 `name`。例如客户端发 `"model": "auto"` 就会路由到名为 `auto` 的模型池。

## 本地开发

### 后端
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 前端（开发模式热更新）
```bash
cd frontend
pnpm install
pnpm dev      # 默认 http://localhost:5173，代理到 8000
```

## 配置项

通过环境变量或 `backend/.env` 配置（见 `backend/app/config.py`）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8080` | 监听端口 |
| `DATABASE_URL` | `sqlite+aiosqlite:////app/data/ai_gateway.db` | 数据库 |
| `ADMIN_PASSWORD` | `admin123` | 管理后台登录密码 |
| `UPSTREAM_TIMEOUT` | `120` | 上游请求超时（秒） |
| `LOG_RETENTION_DAYS` | `30` | 日志保留天数 |
| `STATIC_DIR` | `/app/static` | 前端静态文件目录 |

## License

MIT
