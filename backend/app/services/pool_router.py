"""PoolRouter - 模型池路由策略

根据 Pool.strategy 选择下一个应该调用的 PoolItem：
- priority: 按 priority 升序，选第一个 active item（优先级回退）
- round_robin: 同 priority 之轮询
- weighted: 按 weight 加权随机
- random: 完全随机
"""
import random
from typing import List, Optional

from app.models import PoolItem


class PoolRouter:
    def __init__(self, items: List[PoolItem]):
        # 只考虑 active 的 item
        self.items = [i for i in items if i.is_active]

    def select(self, strategy: str) -> Optional[PoolItem]:
        if not self.items:
            return None

        if strategy == "priority":
            return self._select_priority()
        elif strategy == "round_robin":
            return self._select_round_robin()
        elif strategy == "weighted":
            return self._select_weighted()
        elif strategy == "random":
            return random.choice(self.items)
        else:
            # 默认按 priority
            return self._select_priority()

    def select_all_ordered(self, strategy: str) -> List[PoolItem]:
        """返回按策略排序的全部候选（用于失败回退）"""
        if strategy == "priority":
            return sorted(self.items, key=lambda i: i.priority)
        elif strategy == "round_robin":
            return self._order_round_robin()
        elif strategy == "weighted":
            return self._order_weighted()
        elif strategy == "random":
            shuffled = list(self.items)
            random.shuffle(shuffled)
            return shuffled
        else:
            return sorted(self.items, key=lambda i: i.priority)

    def _select_priority(self) -> Optional[PoolItem]:
        return min(self.items, key=lambda i: i.priority)

    def _select_round_robin(self) -> Optional[PoolItem]:
        # 同 priority 下轮询；这里简化为按 priority 升序后用随机起点轮询
        ordered = sorted(self.items, key=lambda i: (i.priority, i.id))
        return random.choice(ordered)

    def _select_weighted(self) -> Optional[PoolItem]:
        weights = [max(i.weight, 0) for i in self.items]
        if sum(weights) == 0:
            return random.choice(self.items)
        return random.choices(self.items, weights=weights, k=1)[0]

    def _select_random(self) -> Optional[PoolItem]:
        return random.choice(self.items)

    def _order_round_robin(self) -> List[PoolItem]:
        return sorted(self.items, key=lambda i: (i.priority, i.id))

    def _order_weighted(self) -> List[PoolItem]:
        # 按权重降序
        return sorted(self.items, key=lambda i: -i.weight)
