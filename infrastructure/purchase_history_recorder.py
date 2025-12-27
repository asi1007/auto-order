"""
購入履歴記録モジュール
"""

import logging
from datetime import datetime
from typing import List, Dict
from domain.repositories.sheets_repository import SheetsRepository
from domain.value_objects.purchase_history import PurchaseHistoryItem


logger = logging.getLogger(__name__)


def convert_order_to_history_item(order: Dict) -> PurchaseHistoryItem:
    purchase_date = datetime.now().strftime('%Y-%m-%d')
    product_name = order.get('商品名', '')
    url = order.get('購入先URL', '')
    detail = order.get('色・サイズ等指定', '')
    quantity = order.get('発注数', 0)
    price = order.get('単価', 0)
    
    if isinstance(price, str):
        try:
            price = float(price) if price else 0.0
        except ValueError:
            price = 0.0
    
    return PurchaseHistoryItem(
        purchase_date=purchase_date,
        product_name=product_name,
        url=url,
        detail=detail,
        quantity=quantity,
        price=price
    )


def record_purchase_history(
    credentials_file: str,
    history_sheet_url: str,
    order_groups: List[List[Dict]],
    sheet_name: str = None
) -> None:
    if not history_sheet_url:
        logger.warning("購入履歴シートURLが設定されていないため、購入履歴を記録しません")
        return
    
    try:
        logger.info("[ステップ4] 購入履歴を記録しています...")
        logger.info("-" * 60)
        
        repository = SheetsRepository(credentials_file)
        
        total_recorded = 0
        for group in order_groups:
            for order in group:
                try:
                    history_item = convert_order_to_history_item(order)
                    repository.append_purchase_history(
                        history_sheet_url,
                        history_item,
                        sheet_name
                    )
                    total_recorded += 1
                except Exception as e:
                    logger.warning(f"購入履歴の記録に失敗しました（商品: {order.get('商品名', '不明')}）: {e}")
                    continue
        
        logger.info(f"✓ {total_recorded}件の購入履歴を記録しました")
        
    except Exception as e:
        logger.error(f"購入履歴の記録中にエラーが発生しました: {e}")

