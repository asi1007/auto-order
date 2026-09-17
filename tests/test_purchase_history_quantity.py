from __future__ import annotations

from domain.entities.order import Order
from infrastructure.purchase_history_recorder import convert_order_to_history_item


def _material_order(order_quantity: int, lot_size: int) -> Order:
    return Order(
        asin="アクリル説明書",
        material_name="アクリル説明書",
        product_name="アクリル説明書",
        purchase_url="星球彩印",
        order_quantity=order_quantity,
        lot_size=lot_size,
        unit_price=0.03,
        color_size_spec="サイズ91mm*55mm両面白黒印刷157ｇ紙1万枚",
    )


class Test購入履歴の個数:
    """使用資材シートの「発注数」は枚数。ロットサイズを掛けてはいけない。

    2026-09-17 のアクリル説明書 3万枚の発注で、発注ログに 3億 が記録された
    （30,000 × ロットサイズ10,000）。この列は残数計算と最終発注数量の
    参照元なので、狂うと発注判断そのものが壊れる。
    """

    def test_発注数をそのまま個数として記録する(self) -> None:
        item = convert_order_to_history_item(_material_order(30000, 10000), order_number="Y0806-260917001")

        assert item.quantity == 30000

    def test_ロットサイズが1でも同じ(self) -> None:
        item = convert_order_to_history_item(_material_order(500, 1), order_number="Y0806-1")

        assert item.quantity == 500

    def test_ロットサイズ100の資材でも掛けない(self) -> None:
        item = convert_order_to_history_item(_material_order(2500, 100), order_number="Y0806-2")

        assert item.quantity == 2500
