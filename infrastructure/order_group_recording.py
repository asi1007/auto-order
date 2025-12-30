from __future__ import annotations

from typing import Callable, TypeVar

from domain.entities.order import Order
from domain.entities.order_group import OrderGroup


TItem = TypeVar("TItem")


def append_items_from_order_groups(
    *,
    order_groups: list[OrderGroup],
    to_item: Callable[[Order, str], TItem],
    append: Callable[[TItem], None],
    on_error: Callable[[Order, Exception], None] | None = None,
) -> int:
    """
    OrderAutomationの結果（List[OrderGroup]）を走査して、
    (order, order_number) -> item に変換し、append() で追記する共通処理。
    """

    total_recorded = 0
    for result in order_groups:
        order_number = result.order_number or ""
        for order in result.order_group:
            try:
                item = to_item(order, order_number)
                append(item)
                total_recorded += 1
            except Exception as e:
                if on_error is not None:
                    on_error(order, e)
                continue

    return total_recorded


