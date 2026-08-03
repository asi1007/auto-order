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
from infrastructure.exchange_rate_service import convert_cny_to_jpy


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
        def _calc_aggregated_quantity(grouped: list[Order]) -> float:
            quantities = [_calc_purchase_management_quantity(o) for o in grouped]
            quantity_sum = float(sum(quantities))
            quantity_avg = quantity_sum / float(len(grouped))
            return float(int(quantity_avg)) if float(quantity_avg).is_integer() else float(quantity_avg)

        quantity = _calc_aggregated_quantity(grouped)

        unit_prices = [o.unit_price for o in grouped if o.unit_price is not None]
        unit_price: float | None = None
        unit_price_jpy: float | None = None
        if len(unit_prices) == len(grouped):
            # 単価は合計（同一/不一致は問わない。ただし欠損がある場合は空欄）
            unit_price_base = float(sum(float(p) for p in unit_prices))
            # 1商品辺り発注数を掛け算
            qty_per_item = float(max(o.quantity_per_item for o in grouped))
            unit_price = unit_price_base * qty_per_item
            # 単価をJPYに変換
            unit_price_jpy = convert_cny_to_jpy(unit_price)

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
        weight = _join_unique_text([o.weight for o in grouped], sep=" / ")
        height = _join_unique_text([o.height for o in grouped], sep=" / ")
        length = _join_unique_text([o.length for o in grouped], sep=" / ")
        width = _join_unique_text([o.width for o in grouped], sep=" / ")

        # 販売価格は同一ASINなので最初のOrderの値を使う
        selling_price: float | None = None
        for o in grouped:
            if o.selling_price is not None:
                selling_price = o.selling_price
                break

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
                unit_price_jpy=unit_price_jpy,
                selling_price=selling_price,
                material_name=material_name,
                weight=weight,
                height=height,
                length=length,
                width=width,
            )
        )

    return items


def _sum_unit_price_per_main_quantity(
    items: list[PurchaseManagementItem], main: PurchaseManagementItem
) -> float | None:
    """主部材1個を作るのに掛かる原価（= 全部材の総額 ÷ 主部材の数量）を返す。
    補助部材が主部材と同数なら単純な単価の足し算と一致する。
    """
    if any(i.unit_price is None for i in items):
        return None

    main_quantity = float(main.quantity or 0)
    if main_quantity <= 0:
        return None

    total_cost = sum(float(i.quantity or 0) * float(i.unit_price or 0) for i in items)
    return round(total_cost / main_quantity, 2)


def _merge_same_asin_across_groups(items: list[PurchaseManagementItem]) -> PurchaseManagementItem:
    """同一ASINで複数注文番号にまたがる items を1行に統合する。
    Why: Amazon の1製品（同一ASIN）が複数のサプライヤー注文に分かれた場合、
         仕入管理シートは1行で表現するのが正しい運用。原価は主部材+補助部材を
         合算しないと1個あたりの実原価が過少になる。
    Strategy:
      - 注文番号: 改行(\n)区切りで併記
      - 単価: 全部材の総額を主部材の数量で割った「1個あたり実原価」
      - 数量/売値/分類等: 「総額（数量×単価）が最大の item」= 主部材 から採用
      - URL/画像/備考: 全itemから unique 結合
    """
    if len(items) == 1:
        return items[0]

    def _total_cost(i: PurchaseManagementItem) -> float:
        return float(i.quantity or 0) * float(i.unit_price or 0)

    main = max(items, key=_total_cost)
    order_numbers_joined = _join_unique_text([i.order_number for i in items], sep="\n")
    merged_unit_price = _sum_unit_price_per_main_quantity(items, main)
    merged_unit_price_jpy = (
        convert_cny_to_jpy(merged_unit_price) if merged_unit_price is not None else None
    )

    return PurchaseManagementItem(
        purchase_date=main.purchase_date,
        order_number=order_numbers_joined,
        asin=main.asin,
        product_name=main.product_name,
        url=_join_unique_text([i.url for i in items], sep="\n"),
        detail=_join_unique_text([i.detail for i in items], sep=" / "),
        image_text=_join_unique_text([i.image_text for i in items], sep="\n"),
        remark_text=_join_unique_text([i.remark_text for i in items], sep="\n"),
        delivery_category=main.delivery_category,
        quantity=main.quantity,
        unit_price=merged_unit_price,
        unit_price_jpy=merged_unit_price_jpy,
        selling_price=main.selling_price,
        total_price=main.total_price,
        material_name=main.material_name,
        local_price=main.local_price,
        purchase_price_jpy=main.purchase_price_jpy,
        weight=main.weight,
        height=main.height,
        length=main.length,
        width=main.width,
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

        # 全グループ横断で ASIN ごとに items を集約。
        # 同一ASINが複数注文番号にまたがる場合、シート書き込み前に1行に統合する。
        items_by_asin: dict[str, list[PurchaseManagementItem]] = defaultdict(list)
        for result in order_groups:
            # 注文成立していない（order_numberが取れていない）グループは記録対象から除外する。
            if not result.order_number:
                continue
            order_number = result.order_number
            items = _to_purchase_management_items_by_asin(result.order_group, order_number=order_number)
            for item in items:
                items_by_asin[item.asin].append(item)

        merged_items = [_merge_same_asin_across_groups(items) for items in items_by_asin.values()]

        total_recorded = 0
        for item in merged_items:
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


