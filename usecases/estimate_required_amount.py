from __future__ import annotations

from typing import Iterable, Sequence

from domain.entities.order import Order


def estimate_required_amount(order_groups: Iterable[Sequence[Order]]) -> float:
    return sum(
        order.order_quantity * (order.unit_price or 0)
        for group in order_groups
        for order in group
    )
