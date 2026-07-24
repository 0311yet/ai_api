# AI API Gateway - Admin CRUD Bug Fixes (V1.5)

> 2024-07-22: Admin 页面 CRUD 接口全部修复，每个 bug 都导致前端点保存卡死

## Bug 1: POST/PUT /admin/platforms → 500 (MissingGreenlet)

- **严重程度**：高（前端点保存卡死，需手动刷新）
- **错误信息**：
  ```
  ResponseValidationError: 1 validation errors:
  {'type': 'get_attribute_error', 'loc': ('response', 'platform_keys'),
   'msg': "Error extracting attribute: MissingGreenlet: greenlet_spawn has not been called..."}
  ```

### 根因

`PlatformOut` schema 包含 `platform_keys: List[PlatformKeyOut]`。
`create_platform` / `update_platform` 在 `session.commit()` + `session.refresh()` 后直接 return Platform ORM 对象。
FastAPI 用 `response_model=PlatformOut` 序列化时访问懒加载关系 `platform.platform_keys`，触发 SQLAlchemy 的 `MissingGreenlet` 错误（不在 async session 上下文）。

### 修复

`backend/app/routers/platforms.py`：commit 后用 `selectinload` 重新查询再返回。

```python
# 旧
await session.refresh(platform)
return platform

# 新
result = await session.execute(
    select(Platform).where(Platform.id == platform_id)
    .options(selectinload(Platform.platform_keys))
)
platform = result.scalar_one()
return platform
```

- **Commit**：`0a0584e`
- **影响**：`create_platform` 和 `update_platform`

---

## Bug 2: POST /admin/platforms/{id}/keys → 422 (Unprocessable Entity)

- **严重程度**：高（添加 key 保存卡死）
- **错误信息**：
  ```json
  {"detail":[{"type":"missing","loc":["body","platform_id"],"msg":"Field required"}]}
  ```

### 根因

`PlatformKeyCreate` schema 把 `platform_id` 声明为必填 `int`，但前端只传 `{label, api_key, enabled}`。
`platform_id` 实际来自 URL path 参数，body 里不应该重复要求。

### 修复

`backend/app/schemas.py`：把 `platform_id` 改为 Optional。

```python
# 旧
class PlatformKeyCreate(PlatformKeyBase):
    platform_id: int

# 新
class PlatformKeyCreate(PlatformKeyBase):
    platform_id: Optional[int] = None
```

- **Commit**：`cb1da48`

---

## Bug 3: POST /admin/pools/{id}/items → 500 (NOT NULL constraint)

- **严重程度**：高（Pools 页面 "Add Target Model" 卡死）
- **错误信息**：
  ```
  sqlite3.IntegrityError: NOT NULL constraint failed: pool_items.provider_id
  ```

### 根因

数据库表 `pool_items.provider_id` 仍然是 NOT NULL 约束（旧架构遗留，创建表时 provider_id 是必填）。
但新架构下只传 `platform_id`，`provider_id` 为 None → 违反约束。
SQLAlchemy 模型里已经改成 `nullable=True`，但**表级别的 schema 没同步**。

### 修复

`backend/app/database.py` 的 `_ensure_columns()` 加 SQLite 表重建逻辑：

```python
def _sqlite_make_nullable(sync_conn, table, column):
    """SQLite 不能直接 DROP column NOT NULL，所以要重建表：
    1. 取原 CREATE SQL
    2. 删掉目标列的 NOT NULL 约束
    3. rename old → 新建 → copy data → drop old
    """
```

启动时自动检测 `pool_items.provider_id` 是否 NOT NULL，如果是就重建表。
这个操作**幂等**，重启多次也安全。

- **Commit**：`e2f46ad`
- **原理**：SQLite 不支持 `ALTER COLUMN ... DROP NOT NULL`，必须用 rebuild-table 模式迁移

---

## Bug 4: Rates 页面 model 路由冲突

- **严重度**：中（不影响已有功能，访问新增的 /admin/rates/models 端点会 405/422）

### 根因

`PUT /admin/rates/{item_id}` 先声明，`item_id` 没有 type 转换器，能匹配到字符串 "models"。
`PUT /admin/rates/models?model=...` 路由被 `/{item_id}` 抢走 → 尝试把 "models" 当 int 解析 → 422。

而且老路由用 path param `{model}` 不行，因为 model 名能含 `/`（如 `z-ai/glm-5.2`）会将 URL 多出一段。

### 修复

1. 用 query param 传 model：`PUT /admin/rates/models?model=z-ai%2Fglm-5.2`
2. 把 `/models` 和 `/provider/{pid}` 路由**移到 `/{item_id}` 之前**
- **Commit**：`8326743`、`62a693c`
- **教训**：FastAPI 按声明顺序匹配路由，必要时把特殊路由放在通配路由之前

---

## 总结模式：Admin CRUD 卡死的典型原因

前端点保存卡死，基本是后端返回了非 200 状态码但前端没处理 catch：

1. **500 MissingGreenlet** — RelationshipAccessError，需要在端点里用 `selectinload` 显式加载关系
2. **422 Unprocessable Entity** — schema 必填字段问题，路径参数和 body schema 冲突
3. **500 IntegrityError** — 旧表 NOT NULL 约束残留，与迁移后的 SQLAlchemy 模型不同步

下次遇到类似卡死，先看 `docker logs ai-gateway` 的 ERROR 级别日志看 traceback。
