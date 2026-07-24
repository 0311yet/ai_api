# AI API Gateway - 路由 / 负载均衡现状审查 (V1.5)

> 2024-07-22: 分析 Key 之间负载均衡和路由是否实现、能否轮询

## 审查结论

### 当前能做的：Key 级故障切换 ✅

**场景**：NVIDIA NIM 3 个 key，当前用 key-1，key-1 被限流（429）

**流程**：
1. `proxy_json_request` / `proxy_stream_request` 调用 `get_ordered_items(pool, strategy, sticky_id)`
2. `get_routable_items` 把每个 PoolItem × 每个 enabled PlatformKey 展开成独立 `RoutableItem`
3. `for pool_item in ordered:` 循环，开头是排序好的候选列表
4. `state.can_serve(model)` 检查 key 是否在冷却中
5. 若在冷却中 → `continue` 切下一个 key
6. 若 key-2 调用成功 → 返回 200 ✅
7. 若 key-2、key-3 也都被限流 → 返回 502 "All upstreams failed"

**冷却升级**：
- 第 1 次 429 → 冷却 3 秒
- 第 2 次 429 → 冷却 10 秒
- 第 3 次 429 → 冷却 30 秒
- 第 4 次 429 → 冷却 60 秒

冷却到期后 key-1 自动恢复，下次请求又会从它开始（按平台 key_id 固定顺序）。

**结论**：**只配置一个 platform + 多个 key，系统会自动处理故障切换，无需负载均衡配置**。

### 当前没做的：轮询负载均衡 🔴

**场景**：3 个 key，希望 key-1 → key-2 → key-3 → key-1 循环使用。

**当前行为**：正常情况下永远从 key-1 开始用，直到 key-1 被限流才会切换。

## 代码细节

### 实际路由路径

```python
# proxy.py
async def get_ordered_items(pool, strategy, sticky_id) -> Tuple[list, int]:
    from app.services.pool_router import get_routable_items
    items, fallback_count = await get_routable_items(pool.id, "", sticky_id)
    return items, fallback_count
```

**关键点**：`get_ordered_items` **没有根据 `pool.strategy` 分发**！它就是 `get_routable_items` 返回的列表，然后 `proxy_json_request` / `proxy_stream_request` 直接用 `for pool_item in ordered:` 从头试。

也就是说 `pool.strategy` 字段（priority/round_robin/weighted/random）**对代理路径完全无效**，都按相同行为跑：`effective_priority` 升序 + 故障转移。

### `PoolRouter.select()` 是死代码

`pool_router.py` 里的 `select_by_priority`、`select_by_weighted`、`select_by_random`、`select_by_round_robin` 及 `select()` 方法**只有 `select_by_*` 这套选择器方法，但代理路径根本没调用**！

调用方法后选出来一个 item，但然后呢？要自己处理 fallback？——这套半成品 API 当前没有用武之地。

### `select_by_priority` 也有 Bug

```python
# pool_router.py L197
sorted_items = sorted(items, key=lambda i: (-i.effective_priority, i.pool_item_id))
```

负号 `-i.effective_priority` 导致优先级数字**大**的排前面，与 Pools 页面 "Priority (1 = highest)" 的语义相反。

但 `get_routable_items` 自己排序用的是正序：
```python
# pool_router.py L131
routable_items.sort(key=lambda i: (i.effective_priority, i.pool_item_id, i.platform_key_id))
```

这个是对的（数字小的优先）。所以代理路径实际上排序正确，`select_by_priority` 是反向走的死代码 API。

### `select_by_round_robin` 不是真轮询

```python
def select_by_round_robin(self, items, sticky_id=None):
    sorted_items = sorted(items, key=lambda i: i.pool_item_id)
    ...
    for item in sorted_items:
        if item.can_serve[0]:
            return item
```

每次都返回 `pool_item_id` 最小的可用项 — 这等同于 priority 策略，而不是真轮询（应该用计数器轮换）。

### 同优先级多个 key 的排序固定

`get_routable_items` 把同一 PoolItem 下的多个 enabled keys 展开为多个 `RoutableItem`，它们 `effective_priority` 相同（共享 `base_priority`），sort 时按 `platform_key_id` 升序排列。

```python
routable_items.sort(
    key=lambda i: (i.effective_priority, i.pool_item_id, i.platform_key_id)
)
```

意味着 key-1、key-2、key-3 在没有冷却时就固定这个顺序，每次请求永远从 key-1 开始 → "key-1 限流前不会轮询其他 key"。

## 如果要做真负载均衡的改造方向

主要修改 `proxy.py` 的 `get_ordered_items`：

```python
async def get_ordered_items(pool, strategy, sticky_id) -> Tuple[list, int]:
    items, fallback_count = await get_routable_items(pool.id, "", sticky_id)
    
    if strategy == "weighted":
        # random.choices 按 weight 抽
        ...
    elif strategy == "random":
        random.shuffle(items)
    elif strategy == "round_robin":
        # 需要进程内或 redis 维护计数器，每次轮到下一个
        ...
    # priority 不需要额外处理（已升序）
    
    return items, fallback_count
```

**注意**：round_robin 在单 worker 环境下用 `global counter` 即可；多 worker / 多实例需要 Redis 等外部存储共享状态。

## 健康状态相关文件

- `backend/app/services/provider_health.py`：定义 `PlatformKeyHealthState`（per-key 健康 + 冷却 + 惩罚分）
- `backend/app/services/pool_router.py`：`PoolRouter`（路由器，但 `select()` 系列方法是死代码）
- `backend/app/services/proxy.py`：实际代理逻辑，`get_ordered_items` 是真正的入口

## 已做的健康相关功能

- ✅ 429 触发指数退避冷却
- ✅ 失败时自动切换同 Platform 下其他 Keys
- ✅ 同一 platform 下多个 Keys 都会展开成候选 RoutableItem
- ✅ 冷却状态持久化到 DB，重启后能恢复
- ✅ Sticky Session 30 分钟粘性（多轮对话）

## 没做的

- 🔴 轮询负载均衡（priority/round_robin/weighted/random 当前都不起作用）
- 🔴 4xx 错误不应该故障转移（如 400/403，切 key 也没用，浪费配额）
- 🟡 health 页面没有显示 `pool.strategy` 字段（不显示也无所谓，当前是死字段）
