"""
Pool Router: 模型池路由逻辑，支持健康感知、故障转移、粘性会话

重构说明 (v1.3):
- 从 Provider 查询改为 Platform + PlatformKeys 查询
- 实现 per-key 健康状态和负载均衡
- PoolItem 现在指向 Platform，回退时同一 Platform 下切换不同 Keys
"""
import random
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models import Pool, PoolItem, Platform, PlatformKey
from app.services import provider_health as ph

logger = logging.getLogger(__name__)


@dataclass
class RoutableItem:
    """可路由的配置项（Platform + Key + Model）"""
    platform_key_id: int
    platform_id: int
    platform_name: str
    key_label: str
    pool_item_id: int
    model: str
    priority: int
    weight: float
    base_priority: int
    # 直接带上调用上游需要的凭证信息，避免 proxy.py 再去查 DB
    base_url: str = ""
    api_key: str = ""
    is_paid: bool = False

    @property
    def effective_priority(self) -> int:
        """有效优先级 = 基础优先级 - 惩罚分"""
        state = ph.get_platform_key_state(self.platform_key_id)
        if state:
            return state.effective_priority(self.base_priority)
        return self.base_priority

    @property
    def can_serve(self) -> Tuple[bool, str]:
        """检查该 item 是否可服务（健康状态）"""
        state = ph.get_platform_key_state(self.platform_key_id)
        if not state:
            return True, ""
        return state.can_serve(self.model)


class PoolRouter:
    """模型池路由器"""

    def __init__(self, items: List[PoolItem]):
        self.items = items
        # 只考虑 active 的 item
        self.items = [i for i in items if i.is_active]

    @staticmethod
    async def create(pool_id: int) -> "PoolRouter":
        """从数据库加载池配置，创建路由器"""
        async with async_session() as s:
            # 查询 Pool + PoolItem + Platform + (第一个 enabled 的 PlatformKey)
            stmt = (
                select(PoolItem, Platform)
                .join(Platform, PoolItem.platform_id == Platform.id)
                .where(PoolItem.is_active == True, PoolItem.pool_id == pool_id)
                .order_by(PoolItem.priority)
            )
            rows = (await s.execute(stmt)).all()

            return PoolRouter([pool_item for pool_item, _ in rows])

    @staticmethod
    async def get_routable_items(
        pool_id: int,
        model: str = "",
        sticky_platform_key_id: Optional[int] = None,
    ) -> List[RoutableItem]:
        """
        获取可路由的配置项（带 PlatformKeys 和健康状态）

        Args:
            pool_id: 池 ID
            model: 上游模型名（可选，用于过滤）
            sticky_platform_key_id: 粘性会话绑定的 key ID（优先使用）

        Returns:
            RoutableItem 列表（按有效优先级排序）
        """
        async with async_session() as s:
            # 查询 PoolItem + Platform + PlatformKeys
            stmt = (
                select(PoolItem, Platform)
                .join(Platform, PoolItem.platform_id == Platform.id)
                .where(
                    PoolItem.is_active == True,
                    PoolItem.pool_id == pool_id,
                )
                .options(selectinload(Platform.platform_keys))
                .order_by(PoolItem.priority, PoolItem.id)
            )
            if model:
                stmt = stmt.where(PoolItem.model == model)

            rows = (await s.execute(stmt)).all()

            # 转换为 RoutableItem
            routable_items = []
            for pool_item, platform in rows:
                # 获取该 Platform 下所有 enabled 的 PlatformKeys
                enabled_keys = [k for k in platform.platform_keys if k.enabled and k.is_active]

                if not enabled_keys:
                    # 没有 enabled 的 keys，跳过
                    continue

                # 为每个 Key 创建一个 RoutableItem（负载均衡）
                for key in enabled_keys:
                    item = RoutableItem(
                        platform_key_id=key.id,
                        platform_id=platform.id,
                        platform_name=platform.name,
                        key_label=key.label,
                        pool_item_id=pool_item.id,
                        model=pool_item.model,
                        priority=pool_item.priority,
                        weight=pool_item.weight,
                        base_priority=pool_item.priority,
                        base_url=platform.base_url,
                        api_key=key.api_key,
                        is_paid=platform.is_paid,
                    )
                    routable_items.append(item)

                    # 预注册健康状态
                    state = ph.get_platform_key_state(key.id)
                    if state is None:
                        state = ph.PlatformKeyHealthState(
                            platform_key_id=key.id,
                            platform_id=platform.id,
                            key_label=key.label,
                        )
                        ph.register_platform_key_state(state)

            # 按有效优先级排序（值小的优先），同优先级按 pool_item_id 再 key_id
            routable_items.sort(
                key=lambda i: (i.effective_priority, i.pool_item_id, i.platform_key_id)
            )
            return routable_items

    def select_by_priority(
        self,
        items: List[RoutableItem],
        sticky_platform_key_id: Optional[int] = None,
    ) -> Optional[RoutableItem]:
        """
        按优先级选择第一个可用的 RoutableItem

        Args:
            items: 候选列表
            sticky_platform_key_id: 粘性 key（优先使用）

        Returns:
            选中的 RoutableItem，或 None（全部不可用）
        """
        # 如果有粘性 key，优先使用
        if sticky_platform_key_id:
            for item in items:
                if item.platform_key_id == sticky_platform_key_id:
                    can_serve, reason = item.can_serve
                    if can_serve:
                        return item
                    # 粘性 key 不可用，继续尝试其他
                    break

        # 按 effective_priority 排序
        sorted_items = sorted(items, key=lambda i: (-i.effective_priority, i.pool_item_id))

        # 选择第一个可用的
        for item in sorted_items:
            can_serve, reason = item.can_serve
            if can_serve:
                return item

        return None

    def select_by_weighted(
        self,
        items: List[RoutableItem],
        sticky_platform_key_id: Optional[int] = None,
    ) -> Optional[RoutableItem]:
        """
        按权重随机选择（过滤冷却中的和粘性会话）

        Args:
            items: 候选列表
            sticky_platform_key_id: 粘性 key（优先使用）

        Returns:
            选中的 RoutableItem，或 None（全部不可用）
        """
        # 如果有粘性 key，优先使用
        if sticky_platform_key_id:
            for item in items:
                if item.platform_key_id == sticky_platform_key_id:
                    can_serve, reason = item.can_serve
                    if can_serve:
                        return item
                    break

        # 过滤可用的 items
        available = []
        weights = []
        for item in items:
            can_serve, reason = item.can_serve
            if can_serve:
                available.append(item)
                weights.append(max(item.weight, 0))

        if not available:
            return None

        if sum(weights) == 0:
            return random.choice(available)

        return random.choices(available, weights=weights, k=1)[0]

    def select_by_random(
        self,
        items: List[RoutableItem],
        sticky_platform_key_id: Optional[int] = None,
    ) -> Optional[RoutableItem]:
        """随机选择（过滤冷却中的和粘性会话）"""
        # 如果有粘性 key，优先使用
        if sticky_platform_key_id:
            for item in items:
                if item.platform_key_id == sticky_platform_key_id:
                    can_serve, reason = item.can_serve
                    if can_serve:
                        return item
                    break

        available = [item for item in items if item.can_serve[0]]
        return random.choice(available) if available else None

    def select_by_round_robin(
        self,
        items: List[RoutableItem],
        sticky_platform_key_id: Optional[int] = None,
    ) -> Optional[RoutableItem]:
        """轮询选择（按 pool_item_id 排序）"""
        # 简化实现：按 pool_item_id 排序后选择第一个可用
        sorted_items = sorted(items, key=lambda i: i.pool_item_id)

        if sticky_platform_key_id:
            for item in sorted_items:
                if item.platform_key_id == sticky_platform_key_id:
                    can_serve, reason = item.can_serve
                    if can_serve:
                        return item
                    break

        for item in sorted_items:
            can_serve, reason = item.can_serve
            if can_serve:
                return item

        return None

    async def select(
        self,
        strategy: str,
        model: str = "",
        sticky_platform_key_id: Optional[int] = None,
    ) -> Optional[RoutableItem]:
        """根据策略选择一个 RoutableItem"""
        items = await self.get_routable_items(self._pool_id, model, sticky_platform_key_id)

        if not items:
            return None

        if strategy == "priority":
            return self.select_by_priority(items, sticky_platform_key_id)
        elif strategy == "weighted":
            return self.select_by_weighted(items, sticky_platform_key_id)
        elif strategy == "random":
            return self.select_by_random(items, sticky_platform_key_id)
        elif strategy == "round_robin":
            return self.select_by_round_robin(items, sticky_platform_key_id)
        else:
            # 默认 priority
            return self.select_by_priority(items, sticky_platform_key_id)


# ============================================================
# 旧接口（向后兼容迁移期）
# ============================================================

async def get_routable_items(
    pool_id: int,
    model: str = "",
    sticky_platform_key_id: Optional[int] = None,
) -> Tuple[List, int]:
    """
    获取可路由的配置项（兼容旧接口）

    Returns:
        (items, fallback_count)
        fallback_count = 被跳过的 item 数（冷却等）
    """
    items = await PoolRouter.get_routable_items(pool_id, model, sticky_platform_key_id)

    # fallback_count = 不健康的 item 数
    fallback_count = sum(1 for item in items if not item.can_serve[0])

    return items, fallback_count


async def get_available_keys(
    platform_id: int,
    pool_id: int,
    model: str,
) -> List[int]:
    """
    获取指定 Platform 下可用的 PlatformKey ID 列表

    用于 proxy 回退时同 Platform 切换不同 Keys

    Args:
        platform_id: Platform ID
        pool_id: Pool ID（用于过滤 PoolItem）
        model: 模型名

    Returns:
        platform_key_id 列表（按优先级排序）
    """
    async with async_session() as s:
        stmt = (
            select(PoolItem, Platform, PlatformKey)
            .join(Platform, PoolItem.platform_id == Platform.id)
            .join(PlatformKey, Platform.id == PlatformKey.platform_id)
            .where(
                PoolItem.platform_id == platform_id,
                PoolItem.pool_id == pool_id,
                PoolItem.model == model,
                PoolItem.is_active == True,
                PlatformKey.enabled == True,
                PlatformKey.is_active == True,
            )
            .order_by(PoolItem.priority, PlatformKey.id)
        )
        rows = (await s.execute(stmt)).all()

        # 过滤健康的 keys
        healthy_keys = []
        for pool_item, platform, key in rows:
            state = ph.get_platform_key_state(key.id)
            if not state:
                healthy_keys.append(key.id)
                continue
            can_serve, reason = state.can_serve(model)
            if can_serve:
                healthy_keys.append(key.id)

        return healthy_keys