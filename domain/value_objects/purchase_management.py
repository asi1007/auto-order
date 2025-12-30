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
    quantity: int
    image_text: str = ""
    remark_text: str = ""
    unit_price: float | None = None
    total_price: float | None = None
    material_name: str = ""


