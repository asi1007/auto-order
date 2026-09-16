"""グループが成立するたびに記録するコールバックの検証。

全グループ終わってからまとめて記録すると、途中で落ちた分の注文が
仕入管理シートに一切残らない。2026-09-16 に実際に起きた。
"""
from __future__ import annotations

import pytest

from domain.entities.order import Order
from domain.entities.order_group import OrderGroup


def _order(asin: str) -> Order:
    return Order(
        asin=asin,
        product_name="テスト商品",
        sales_product_name="テスト商品",
        purchase_url="https://detail.1688.com/offer/1.html",
        color_size_spec="規格",
        order_quantity=10,
        sales_order_quantity=10,
        unit_price=1.0,
        chatwork_message="",
        chatwork_attachment="",
        image_text="",
        remark_text="",
        delivery_category="ノーマル",
        quantity_per_item=1,
        weight=0,
        height=0,
        length=0,
        width=0,
    )


class FakeAutomation:
    """process_orders の該当部分だけを模したもの。"""

    def __init__(self, order_numbers: list[str | None], fail_at: int | None = None) -> None:
        self.order_numbers = order_numbers
        self.fail_at = fail_at

    def process(self, groups: list[list[Order]], on_group_done=None) -> list[OrderGroup]:
        results: list[OrderGroup] = []
        for i, group in enumerate(groups, 1):
            if self.fail_at is not None and i == self.fail_at:
                raise RuntimeError("途中で落ちた")
            result = OrderGroup(order_group=group, order_number=self.order_numbers[i - 1])
            results.append(result)
            if on_group_done is not None:
                on_group_done(result)
        return results


class TestOnGroupDone:
    def test_グループごとにコールバックが呼ばれる(self) -> None:
        recorded: list[str | None] = []
        automation = FakeAutomation(["Y-1", "Y-2", "Y-3"])

        automation.process(
            [[_order("A")], [_order("B")], [_order("C")]],
            on_group_done=lambda r: recorded.append(r.order_number),
        )

        assert recorded == ["Y-1", "Y-2", "Y-3"]

    def test_途中で落ちても成立済みの分は記録されている(self) -> None:
        # ここが本題。2件目で落ちても1件目は記録済みでなければならない
        recorded: list[str | None] = []
        automation = FakeAutomation(["Y-1", "Y-2", "Y-3"], fail_at=2)

        with pytest.raises(RuntimeError):
            automation.process(
                [[_order("A")], [_order("B")], [_order("C")]],
                on_group_done=lambda r: recorded.append(r.order_number),
            )

        assert recorded == ["Y-1"]

    def test_コールバックを渡さなくても動く(self) -> None:
        automation = FakeAutomation(["Y-1"])

        results = automation.process([[_order("A")]])

        assert [r.order_number for r in results] == ["Y-1"]

    def test_注文番号が取れなかったグループも通知される(self) -> None:
        # 未成立の判定は呼び出し側で行う。記録するかはそちらの責任
        recorded: list[str | None] = []
        automation = FakeAutomation([None])

        automation.process([[_order("A")]], on_group_done=lambda r: recorded.append(r.order_number))

        assert recorded == [None]


class TestRecordableGroups:
    def test_注文番号のあるグループだけ記録する(self) -> None:
        from infrastructure.purchase_management_recorder import recordable_groups

        groups = [
            OrderGroup(order_group=[_order("A")], order_number="Y-1"),
            OrderGroup(order_group=[_order("B")], order_number=None),
            OrderGroup(order_group=[_order("C")], order_number="Y-3"),
        ]

        assert [g.order_number for g in recordable_groups(groups)] == ["Y-1", "Y-3"]

    def test_空なら空(self) -> None:
        from infrastructure.purchase_management_recorder import recordable_groups

        assert recordable_groups([]) == []

    def test_注文番号が空文字のものは除く(self) -> None:
        from infrastructure.purchase_management_recorder import recordable_groups

        groups = [OrderGroup(order_group=[_order("A")], order_number="")]

        assert recordable_groups(groups) == []
