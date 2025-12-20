"""
Googleシートから発注情報を読み込むモジュール
"""

import pandas as pd
from typing import List, Dict
from domain.repositories.sheets_repository import SheetsRepository
from domain.services.order_merge_service import OrderMergeService


class NoOrderDataException(Exception):
    pass


class SheetsReader:
    def __init__(self, credentials_file: str):
        self._repository = SheetsRepository(credentials_file)
        self._merge_service = OrderMergeService()
    
    @property
    def client(self):
        return self._repository.client
    
    def read_sales_sheet(self, sheet_url: str, sheet_name: str = "売上/日") -> pd.DataFrame:
        sales_sheet = self._repository.read_sales_sheet(sheet_url, sheet_name)
        return sales_sheet.to_dataframe()
    
    def read_purchase_sheet(self, sheet_url: str, sheet_name: str = "仕入情報") -> pd.DataFrame:
        purchase_info_sheet = self._repository.read_purchase_info_sheet(sheet_url, sheet_name)
        return purchase_info_sheet.to_dataframe()
    
    def merge_data(self, sales_df: pd.DataFrame, purchase_df: pd.DataFrame) -> List[Dict]:
        from domain.value_objects.sales_sheet import SalesSheet
        from domain.value_objects.purchase_info_sheet import PurchaseInfoSheet
        
        # DataFrameからValueObjectに変換
        sales_sheet = SalesSheet.from_dataframe(sales_df)
        purchase_info_sheet = PurchaseInfoSheet.from_dataframe(purchase_df)
        
        # Serviceを使ってマージ
        return self._merge_service.merge(sales_sheet, purchase_info_sheet)


def group_orders_by_url(order_list: List[Dict], max_items_per_group: int = 5) -> List[List[Dict]]:
    import logging
    from collections import defaultdict
    
    logger = logging.getLogger(__name__)
    logger.info("[ステップ2] 購入先URLごとにグループ化しています...")
    logger.info("-" * 60)
    
    # 購入先URLごとにグループ化（URLを正規化）
    url_groups = defaultdict(list)
    for order in order_list:
        # URLを正規化（前後の空白を削除、末尾のスラッシュを削除）
        normalized_url = order['購入先URL'].strip().rstrip('/')
        url_groups[normalized_url].append(order)
    
    # デバッグ情報: URL別の商品数を表示
    for url, orders in url_groups.items():
        print(f"  {url}: {len(orders)}商品")
    
    # 各グループを最大商品数ごとに分割
    grouped_orders = []
    for url, orders in url_groups.items():
        # 最大商品数ごとに分割
        for i in range(0, len(orders), max_items_per_group):
            group = orders[i:i + max_items_per_group]
            grouped_orders.append(group)
    
    total_groups = len(grouped_orders)
    total_items = sum(len(group) for group in grouped_orders)
    print(f"✓ {total_items}件の商品を{total_groups}グループにまとめました")
    
    # グループの詳細を表示
    for i, group in enumerate(grouped_orders, 1):
        url = group[0]['購入先URL']
        print(f"  グループ{i}: {url} ({len(group)}商品)")
    
    # 発注データの確認
    logger.info("[発注データ一覧]")
    logger.info("-" * 60)
    for i, group in enumerate(grouped_orders, 1):
        logger.info("グループ%s: %s", i, group[0]["購入先URL"])
        for j, order in enumerate(group, 1):
            logger.info(
                "  商品%s: %s (ASIN: %s)",
                j,
                order["商品名"],
                order["ASIN"],
            )
            logger.info(
                "         発注数: %s, 単価: %s",
                order["発注数"],
                order["単価"],
            )
    
    # ユーザーに確認
    logger.info("")
    logger.info(
        "%sグループ（合計%s商品）の注文を処理します...",
        total_groups,
        total_items,
    )
    logger.info("処理を開始します")
    
    return grouped_orders


def get_order_data(credentials_file: str, sales_url: str, purchase_url: str) -> List[Dict]:
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("[ステップ1] Googleシートから発注データを読み込んでいます...")
    logger.info("-" * 60)
    
    reader = SheetsReader(credentials_file)
    
    sales_df = reader.read_sales_sheet(sales_url)
    purchase_df = reader.read_purchase_sheet(purchase_url)
    
    order_list = reader.merge_data(sales_df, purchase_df)
    
    if not order_list:
        logger.info("処理する発注データがありません")
        raise NoOrderDataException("処理する発注データがありません")
    
    return order_list

