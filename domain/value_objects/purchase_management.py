"""
仕入管理シート向けのValueObject
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PurchaseManagementItem:
    purchase_date: str
    order_number: str
    asin: str
    product_name: str
    url: str
    detail: str
    # 仕入管理シート上の「数量/購入数」等に記録する値（平均値になる場合があるためfloatを許容）
    quantity: float
    image_text: str = ""
    remark_text: str = ""
    delivery_category: str = ""
    unit_price: float | None = None
    unit_price_jpy: float | None = None
    selling_price: float | None = None
    total_price: float | None = None
    material_name: str = ""
    # 現地価格（元）
    local_price: float | None = None
    # 購入価格（円換算）
    purchase_price_jpy: float | None = None
    weight: str = ""
    height: str = ""
    length: str = ""
    width: str = ""


