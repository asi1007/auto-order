from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    asin: str
    product_name: str
    purchase_url: str
    order_quantity: int
    # 売上/日（Sales）シートに記録されている発注量（仕入管理への記録に使用）
    sales_order_quantity: int = 0
    sales_product_name: str = ""
    color_size_spec: str = ""
    unit_price: float | None = None
    chatwork_message: str = ""
    chatwork_attachment: str = ""
    image_text: str = ""
    remark_text: str = ""
    delivery_category: str = ""
    material_name: str = ""
    lot_size: int = 1
    quantity_per_item: int = 1
    selling_price: float | None = None
    weight: str = ""
    height: str = ""
    length: str = ""
    width: str = ""

    @property
    def normalized_purchase_url(self) -> str:
        return str(self.purchase_url).strip().rstrip("/")

    @property
    def unit_price_for_form(self) -> str:
        if self.unit_price is None:
            return ""
        if self.unit_price <= 0:
            return ""
        # フォーム入力は文字列でOK
        if float(self.unit_price).is_integer():
            return str(int(self.unit_price))
        return str(self.unit_price)


