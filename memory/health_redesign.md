# AI API Gateway - Health Page Redesign (V1.4→V1.5)

> 2024-07-22: Health 页面从 pool→model 嵌套改为 platform→keys 垂直列表

## 变更原因

用户反馈：Health 页面每个大块太宽，希望两个大块并排显示；每个大块内 keys 竖着放，不并排。

## 改动内容

### 后端（V1.5）

#### 新增接口：`/admin/health/platforms`
- **路由**：`GET /admin/health/platforms`
- **返回**：平台 → keys 结构（去掉了 model 层）
- **文件**：`backend/app/routers/health.py`

#### 新增 Schema
- `PlatformsHealthOut`：平台列表
- `PlatformHealthItem`：单个平台（含 platform_keys）
- `PlatformHealthKeyItem`：单个 key 的 rate_window（跨所有 model 聚合）

#### 修复 Bug：`PlatformKeyCreate.platform_id` 必填
- **问题**：POST `/admin/platforms/{id}/keys` 返回 422
- **原因**：`PlatformKeyCreate` schema 把 `platform_id` 声明为必填 `int`，但前端只传 `{label, api_key, enabled}`，`platform_id` 来自 URL
- **修复**：改为 `Optional[int] = None`，路由用 URL 参数

### 前端（V1.5）

#### Health.vue 完全重写
- **布局**：
  - 大块两列显示：`grid-template-columns: repeat(auto-fill, minmax(560px, 1fr))`
  - 每个大块内 keys 竖排：`flex flex-col gap-2`
- **数据**：调用 `healthAPI.platforms()` 读取 `/admin/health/platforms`
- **自动刷新**：3 秒 `setInterval` 轮询

#### Platforms.vue
- **新增**：删除平台按钮（红色 Del）
- **新增**：加载转圈 spinner（`NSpin`）
- **优化**：Key CRUD 局部刷新 `reloadPlatform(pid)`，不触发全页重载

### 数据流变更

**旧数据流**：
```
Platform → PoolItem → model
  → healthAPI.overview() 返回 per-model rate_window
```

**新数据流**：
```
Platform → platform_keys（懒加载）
  → healthAPI.platforms() 聚合所有 platform_keys 的 rate_window → 每个 key 一行
```

## Commit 历史

| Commit | 描述 |
|--------|------|
| `63e7652` | stream 请求补 record_request |
| `6d380c8` | 流式请求用 resolved model |
| `87f8db8` | health platforms endpoint + UI |
| `9941e47` | frontend dist build |
| `94576a5` | docstring fix |
| `132b5da` | vertical layout |
| `0a0584e` | fix: MissingGreenlet on POST/PUT /admin/platforms |
| `cb1da48` | fix: PlatformKeyCreate.platform_id required → Optional |
| `6fb17df` | ui: Platforms page - delete button + loading spin |
| `ab40170` | ui: Platforms - local reload after key CRUD |
| `5260dd9` | feat: Rates page - per-model pricing |
| `8326743` | fix: rates PUT uses query param |
| `62a693c` | fix: move /{item_id} route after /models |
| `e2f46ad` | fix: pool_items.provider_id NOT NULL → nullable via SQLite rebuild |

## 测试验证

```bash
# 检查健康数据流
curl -s http://localhost:8080/admin/health/platforms \
  -H "X-Admin-Key: sk-admin-123456" | python3 -m json.tool | head -50

# 验证负载切换（3个 key，1个限流）
# 1. 调用若干次直到 key-1 进入冷却
# 2. 继续调用，观察是否自动切换到 key-2/key-3
```

## 注意事项

- Health 页面 keys 的 rate_window 是**跨所有 models 聚合**的（`sum(sw.count()) + sum(sw.tokens())`）
- Platform 的 `is_paid` 标记决定收费与否，不直接体现在 health 页面
- 部署时前端 dist 已提交到 git，Dockerfile 直接 COPY `frontend/dist ./static`
