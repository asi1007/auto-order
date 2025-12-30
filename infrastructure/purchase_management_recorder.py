"""
仕入管理シート記録モジュール
"""

from __future__ import annotations

import logging
from datetime import datetime

from domain.entities.order_group import OrderGroup
from domain.entities.order import Order
from domain.value_objects.purchase_management import PurchaseManagementItem
from infrastructure.order_group_recording import append_items_from_order_groups
from infrastructure.repositories import BaseSheetsRepository, SheetsPurchaseManagementRepository


logger = logging.getLogger(__name__)


def _to_purchase_management_item(order: Order, *, order_number: str) -> PurchaseManagementItem:
    purchase_date = datetime.now().strftime("%Y-%m-%d")
    quantity = int(order.order_quantity) * int(order.lot_size or 1)
    unit_price = order.unit_price
    total_price = None
    if unit_price is not None:
        total_price = float(unit_price) * float(quantity)

    return PurchaseManagementItem(
        purchase_date=purchase_date,
        order_number=order_number,
        asin=order.asin,
        # 仕入管理の商品名列はSalesシートの商品名
        product_name=order.sales_product_name or order.product_name,
        url=order.purchase_url,
        detail=order.color_size_spec,
        image_text=order.image_text,
        remark_text=order.remark_text,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        material_name=order.material_name,
    )


def record_purchase_management(
    credentials_file: str,
    management_sheet_url: str,
    order_groups: list[OrderGroup],
    management_sheet_name: str | None = None,
) -> None:
    assert credentials_file, "credentials_fileは必須です"
    assert management_sheet_url, "management_sheet_urlは必須です"
    assert order_groups is not None, "order_groupsはNoneであってはなりません"

    try:
        logger.info("[ステップ4] 仕入管理シートに記録しています...")
        base = BaseSheetsRepository(credentials_file)
        repository = SheetsPurchaseManagementRepository(
            credentials_file=credentials_file,
            sheet_url=management_sheet_url,
            sheet_name=management_sheet_name,
            client=base.client,
        )

        total_recorded = append_items_from_order_groups(
            order_groups=order_groups,
            to_item=lambda order, order_number: _to_purchase_management_item(order, order_number=order_number),
            append=repository.append,
            on_error=lambda order, e: logger.warning(
                "仕入管理の記録に失敗しました（商品: %s）: %s",
                getattr(order, "product_name", "不明"),
                e,
            ),
        )

        logger.info("✓ %s件の仕入管理を記録しました", total_recorded)
    except Exception as e:
        logger.error("仕入管理の記録中にエラーが発生しました: %s", e)


