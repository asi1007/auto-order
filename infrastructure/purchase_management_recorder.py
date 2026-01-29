"""
仕入管理シート記録モジュール
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime

from domain.entities.order_group import OrderGroup
from domain.entities.order import Order
from domain.value_objects.purchase_management import PurchaseManagementItem
from infrastructure.repositories import BaseSheetsRepository, SheetsPurchaseManagementRepository


logger = logging.getLogger(__name__)


def _calc_purchase_management_quantity(order: Order) -> int:
    base_qty = int(order.sales_order_quantity) if int(order.sales_order_quantity) > 0 else int(order.order_quantity)
    return base_qty * int(order.lot_size or 1)


def _join_unique_text(values: list[str], *, sep: str) -> str:
    unique: list[str] = []
    for v in values:
        s = str(v or "").strip()
        if not s:
            continue
        if s in unique:
            continue
        unique.append(s)
    return sep.join(unique)


def _to_purchase_management_items_by_asin(orders: list[Order], *, order_number: str) -> list[PurchaseManagementItem]:
    """
    仕入管理シートには「ASINごとに1行」で記載したいので、同一ASINのOrderを集約してPurchaseManagementItemを作る。
    """
    purchase_date = datetime.now().strftime("%Y-%m-%d")

    by_asin: dict[str, list[Order]] = defaultdict(list)
    for o in orders:
        by_asin[str(o.asin)].append(o)

    items: list[PurchaseManagementItem] = []
    for asin, grouped in by_asin.items():
        quantities = [_calc_purchase_management_quantity(o) for o in grouped]
        quantity_sum = float(sum(quantities))
        quantity_avg = quantity_sum / float(len(grouped))
        quantity: float
        quantity = float(int(quantity_avg)) if float(quantity_avg).is_integer() else float(quantity_avg)

        unit_prices = [o.unit_price for o in grouped if o.unit_price is not None]
        unit_price: float | None = None
        if len(unit_prices) == len(grouped):
            # 単価は合計（同一/不一致は問わない。ただし欠損がある場合は空欄）
            unit_price = float(sum(float(p) for p in unit_prices))

        total_prices = []
        for o in grouped:
            if o.unit_price is None:
                total_prices = []
                break
            total_prices.append(float(o.unit_price) * float(_calc_purchase_management_quantity(o)))
        total_price: float | None = float(sum(total_prices)) if total_prices else None

        product_name = _join_unique_text(
            [(o.sales_product_name or o.product_name) for o in grouped],
            sep=" / ",
        )
        url = _join_unique_text([o.purchase_url for o in grouped], sep="\n")
        detail = _join_unique_text([o.color_size_spec for o in grouped], sep=" / ")
        image_text = _join_unique_text([o.image_text for o in grouped], sep="\n")
        remark_text = _join_unique_text([o.remark_text for o in grouped], sep="\n")
        delivery_category = _join_unique_text([o.delivery_category for o in grouped], sep=" / ")
        material_name = _join_unique_text([o.material_name for o in grouped], sep=" / ")

        items.append(
            PurchaseManagementItem(
                purchase_date=purchase_date,
                order_number=order_number,
                asin=asin,
                # 仕入管理の商品名列はSalesシートの商品名
                product_name=product_name,
                url=url,
                detail=detail,
                image_text=image_text,
                remark_text=remark_text,
                delivery_category=delivery_category,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                material_name=material_name,
            )
        )

    return items


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

        total_recorded = 0
        for result in order_groups:
            order_number = result.order_number or ""
            items = _to_purchase_management_items_by_asin(result.order_group, order_number=order_number)
            for item in items:
                try:
                    repository.append(item)
                    total_recorded += 1
                except Exception as e:
                    logger.warning(
                        "仕入管理の記録に失敗しました（ASIN: %s）: %s",
                        getattr(item, "asin", "不明"),
                        e,
                    )
                    continue

        logger.info("✓ %s件の仕入管理を記録しました", total_recorded)
    except Exception as e:
        logger.error("仕入管理の記録中にエラーが発生しました: %s", e)


