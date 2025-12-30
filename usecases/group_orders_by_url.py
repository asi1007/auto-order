from __future__ import annotations

import logging
from collections import defaultdict
from domain.entities.order import Order


logger = logging.getLogger(__name__)


def group_orders_by_url(order_list: list[Order], max_items_per_group: int = 5) -> list[list[Order]]:
    logger.info("[ステップ2] 購入先URLごとにグループ化しています...")

    url_groups: dict[str, list[Order]] = defaultdict(list)
    for order in order_list:
        normalized_url = order.normalized_purchase_url
        url_groups[normalized_url].append(order)

    for url, orders in url_groups.items():
        logger.info("  %s: %s商品", url, len(orders))

    grouped_orders: list[list[Order]] = []
    for url, orders in url_groups.items():
        for i in range(0, len(orders), max_items_per_group):
            group = orders[i : i + max_items_per_group]
            grouped_orders.append(group)

    total_groups = len(grouped_orders)
    total_items = sum(len(group) for group in grouped_orders)
    logger.info("✓ %s件の商品を%sグループにまとめました", total_items, total_groups)

    for i, group in enumerate(grouped_orders, 1):
        url = group[0].purchase_url
        logger.info("  グループ%s: %s (%s商品)", i, url, len(group))

    logger.info("[発注データ一覧]")
    logger.info("-" * 60)
    for i, group in enumerate(grouped_orders, 1):
        logger.info("グループ%s: %s", i, group[0].purchase_url)
        for j, order in enumerate(group, 1):
            logger.info("  商品%s: %s (ASIN: %s)", j, order.product_name, order.asin)
            logger.info("         発注数: %s, 単価: %s", order.order_quantity, order.unit_price_for_form)

    logger.info("")
    logger.info("%sグループ（合計%s商品）の注文を処理します...", total_groups, total_items)
    logger.info("処理を開始します")

    return grouped_orders


