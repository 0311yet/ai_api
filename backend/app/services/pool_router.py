"""PoolRouter - 模型池路由策略

根据 Pool.strategy 选择下一个应该调用的 PoolItem：
- priority: 按 priority 升序，选第一个 active item（优先级回退）
- round_robin: 同 priority 之轮询
- weighted: 按 weight 加权随机
- random: 完全随机

健康感知增强（可选，默认关闭）：
- 按 effective_priority 排序（base_priority - penalty_score）
- 冷却中的 Provider 排在最末
"""
import random
from typing import List, Optional, Set, Tuple

from app.models import PoolItem
from app.services import provider_health as ph


class PoolRouter:
    def __init__(self, items: List[PoolItem]):
        # 只考虑 active 的 item
        self.items = [i for i in items if i.is_active]

    def select(self, strategy: str) -> Optional[PoolItem]:
        return self._select_by_strategy(strategy)

    def select_all_ordered(self, strategy: str) -> List[PoolItem]:
        """返回按策略排序的全部候选（用于失败回退），不检查健康状态"""
        if strategy == "priority":
            return sorted(self.items, key=lambda i: i.priority)
        elif strategy == "round_robin":
            return sorted(self.items, key=lambda i: (i.priority, i.id))
        elif strategy == "weighted":
            return sorted(self.items, key=lambda i: -i.weight)
        elif strategy == "random":
            shuffled = list(self.items)
            random.shuffle(shuffled)
            return shuffled
        else:
            return sorted(self.items, key=lambda i: i.priority)

    def select_all_routable(
        self,
        strategy: str,
        sticky_provider_id: Optional[int] = None,
    ) -> List[PoolItem]:
        """
        返回按策略排序的候选（健康感知）。
        - 冷却中的 item 移到末尾
        - 惩罚分高的 item 排后（priority 策略时 effective_priority = priority - penalty）
        - sticky_provider 优先（如果它可用）
        返回 (list[PoolItem], fallback_count)
        fallback_count = 被跳过的 item 数（冷却等）
        """
        items = list(self.items)
        if not items:
            return [], 0

        def sort_key(item: PoolItem) -> Tuple[int, int, int]:
            """
            priority 排序：
            (group, effective_priority, item_id)
            group=0: 正常可用
            group=1: 冷却中
            group=2: 被惩罚到不可用
            """
            pstate = ph.get_provider_state(item.provider_id)
            if pstate and pstate.is_in_cooldown():
                # 冷却中，降权但不排除（可能冷却快过期了）
                return (1, item.priority, item.id)
            if pstate and pstate.penalty_score >= 10:
                # 惩罚分达到上限，降权
                return (2, item.priority, item.id)
            # 正常：优先考虑 sticky
            is_sticky = 0 if (sticky_provider_id and item.provider_id == sticky_provider_id) else 1
            effective = item.priority
            if pstate:
                effective = item.priority - pstate.penalty_score
            return (0, effective * 10 + is_sticky, item.id)   # is_sticky 小的排前面

        # 先按 strategy 得到候选列表，再按 sort_key 排序
        base = self.select_all_ordered(strategy)
        sorted_items = sorted(base, key=sort_key)
        skipped = len(base) - len(sorted_items)
        return sorted_items, skipped

    def select_by_weighted_with_health(self) -> Optional[PoolItem]:
        """weighted 策略：过滤冷却中的 item 后加权随机"""
        available = []
        weights = []
        for item in self.items:
            pstate = ph.get_provider_state(item.provider_id)
            if pstate and pstate.is_in_cooldown():
                continue
            available.append(item)
            weights.append(max(item.weight, 0))
        if not available:
            return None
        if sum(weights) == 0:
            return random.choice(available)
        return random.choices(available, weights=weights, k=1)[0]

    def _select_by_strategy(self, strategy: str) -> Optional[PoolItem]:
        if strategy == "priority":
            return min(self.items, key=lambda i: i.priority)
        elif strategy == "round_robin":
            return random.choice(sorted(self.items, key=lambda i: (i.priority, i.id)))
        elif strategy == "weighted":
            return self.select_by_weighted_with_health()
        elif strategy == "random":
            return random.choice(self.items)
        else:
            return min(self.items, key=lambda i: i.priority)

