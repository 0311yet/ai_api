# AI API Gateway 项目记忆文件

> 最后更新：2026-07-22

## 项目基本信息

| 项目 | 内容 |
|------|------|
| 项目名 | AI API Gateway |
| 仓库 | git@github.com:0311yet/ai_api.git |
| 本地目录 | D:\workplace\vibe code\PI\ai_api |
| 旧目录（已停更） | D:\workplace\vibe code\PI\test\ai_gateway |
| 技术栈 | Vue 3 + Vite + FastAPI + SQLite (async) + SQLAlchemy 2.0 |
| 当前版本 | fc53cc0 (feat: 5 大高级功能实现完成) |

## Git 提交历史

| Hash | 说明 |
|------|------|
| `fc53cc0` | feat: 5 大高级功能实现完成 |
| `02c58c3` | 添加 README |
| `c190e71` | 迁移到 Vue 3 + Vite + FastAPI 新架构 |
| `cd5d84a` | 保存旧项目状态（迁移前快照） |
| `73a9fa0` | Initial commit: AI API Gateway |

## 服务器信息

| 项目 | 内容 |
|------|------|
| 主机 | 154.9.228.163 |
| 用户 | root |
| 密码 | njZkKQkM23KjApWj |
| 项目目录 | /root/apps/ai_gateway/ |
| 容器名 | ai-gateway |
| API 端口 | 8080 |
| Admin 密码 | sk-admin-123456 |

## 项目架构

```
ai_api/
├── backend/app/
│   ├── main.py              # FastAPI 入口，lifespan 管理
│   ├── config.py            # Pydantic Settings
│   ├── database.py          # SQLAlchemy async + SQLite WAL
│   ├── middleware.py        # get_admin_key_optional / verify_admin
│   ├── schemas.py           # 所有 Pydantic 模型
│   ├── models/__init__.py   # 8 张表（含新增的 rate_limit_events、provider_cooldowns）
│   ├── routers/
│   │   ├── auth.py          # /admin/login, /admin/verify
│   │   ├── providers.py     # Provider CRUD
│   │   ├── pools.py         # Pool + PoolItem CRUD
│   │   ├── keys.py          # ClientKey CRUD
│   │   ├── logs.py          # 请求日志查询
│   │   ├── stats.py         # Dashboard / Timeseries / By-Model / Daily
│   │   ├── proxy.py         # /v1/chat/completions, /v1/messages（Anthropic 格式）
│   │   └── health.py        # /admin/health/overview, /admin/health/rate-limit/{id}
│   └── services/
│       ├── pool_router.py   # 路由选择（cooldown/penalty 过滤 + effective_priority 排序）
│       ├── proxy.py         # 代理核心（429 检测、冷却升级、惩罚、StickySession）
│       └── provider_health.py # ProviderState、SlidingWindow、StickySessionManager
└── frontend/src/
    ├── views/               # Dashboard/Providers/Pools/Keys/Logs/Stats/Login
    ├── components/          # StatCard/TopBar/MainLayout 等
    ├── router/index.ts     # Vue Router 配置
    ├── stores/auth.ts      # Pinia 认证状态
    └── api/index.ts         # Axios API 封装
```

## 已实现功能

### 基础功能
- Provider 管理（CRUD）
- Pool + PoolItem 管理（CRUD）
- ClientKey 管理（CRUD + 使用量统计）
- 请求日志查询（分页）
- 统计面板（Dashboard / Timeseries / By-Model / Daily）
- Anthropic `/v1/messages` 格式支持
- OpenAI `/v1/chat/completions` 格式支持

### 5 大高级功能（参考 FreeLLMAPI）
1. **自动路由 + 故障转移**：429 → 重试下一个；5xx → 重试下一个
2. **滑动窗口限流**：1440 桶/Provider（24h），记录 RPM/RPD/TPM/TPD
3. **动态惩罚路由**：429 → penalty+3；每 2 分钟衰减 -1；影响 effective_priority
4. **冷却升级策略**：strike 1→2min, 2→10min, 3→1h, 4→24h
5. **Sticky Session**：多轮对话（messages 含 assistant）→ 30 分钟绑定同一 Provider

## 数据库表结构

| 表名 | 说明 |
|------|------|
| `providers` | 上游 Provider（base_url, api_key, models, is_active） |
| `pools` | Pool 定义（name, strategy: priority/round_robin/weighted/random, is_active） |
| `pool_items` | Pool ↔ Provider 绑定（model, priority, weight, is_active） |
| `client_keys` | 客户端 Key（key, pool_id, allowed_models, request_count, total_tokens） |
| `request_logs` | 请求日志（status, tokens, latency, error_message, ip, is_stream） |
| `rate_limit_events` | 限流事件（新增，event_type='limit'） |
| `provider_cooldowns` | 冷却状态（新增，cooldown_until, strike_count, penalty_score） |
| `daily_stats` | 每日统计（后台任务生成） |

## 重要决策记录

### 数据库
- 使用 SQLite + WAL 模式，避免读写阻塞
- 避免 `cast(..., Date)`，改用 `func.date()` 返回纯字符串
- 复用 `request_logs` 而非新建 `rate_limit_usage` 表

### 新功能策略
- 默认关闭（无行为改变），向后兼容
- 所有状态在内存中管理，后台任务定期写 SQLite
- 冷却时间映射：`{1: 120, 2: 600, 3: 3600, 4: 86400}`
- 惩罚分衰减：后台 `asyncio` 定时器每 2 分钟扫描

### Sticky Session
- 识别：检测 `messages[]` 中是否存在 `assistant` 角色
- Session key：`SHA1(ip + first_message + session_id)`
- TTL：1800 秒（30 分钟）

## 已知问题 / 待完成

1. **pool_items 为空**：需要手动添加 Provider 到 Pool（`POST /admin/pools/1/items`）
2. **前端 Health 页面**：未实现显示冷却/惩罚/限流状态的 UI
3. **限流阈值配置**：未实现 CRUD 配置接口
4. **Provider 选择策略**：round_robin / weighted / random 未完整实现
5. **请求体大小限制**：未实现
6. **超时重试次数配置**：未实现

## 部署命令备忘

```bash
# SSH 连接
ssh root@154.9.228.163

# 查看日志
docker logs ai-gateway -f

# 重启容器
docker restart ai-gateway

# 查看数据库（容器内）
docker exec ai-gateway python3 -c "import sqlite3; c = sqlite3.connect('/app/data/ai_gateway.db'); print(c.execute('SELECT * FROM pool_items').fetchall())"

# 测试 API
curl http://localhost:8080/health
curl -X POST http://localhost:8080/admin/login -H "Content-Type: application/json" -d '{"password": "sk-admin-123456"}'

# 本地构建前端
cd frontend && pnpm install && pnpm build

# 本地测试后端语法
cd backend && python -c "import app.main; print('OK')"
```

## 开发规范

- `edit`/`write`/`read` 工具用于本地文件
- 部署到服务器必须用 `ssh_exec` + SFTP 或 `docker cp`
- 每次 `docker cp` 后必须 `docker restart ai-gateway`
- Git commit 前本地验证语法：`cd backend && python -c "import app.main"`
- 新功能默认关闭，向后兼容