"""
購入履歴記録モジュール
"""

import logging
from datetime import datetime
from typing import List, Dict
from infrastructure.repositories import BaseSheetsRepository, SheetsPurchaseHistoryRepository
from domain.value_objects.purchase_history import PurchaseHistoryItem


logger = logging.getLogger(__name__)


def convert_order_to_history_item(order: Dict) -> PurchaseHistoryItem:
    assert order is not None, "orderはNoneであってはなりません"
    assert '商品名' in order, "orderに商品名がありません"
    assert '購入先URL' in order, "orderに購入先URLがありません"
    assert '発注数' in order, "orderに発注数がありません"
    
    purchase_date = datetime.now().strftime('%Y-%m-%d')
    order_number = order.get('注文番号', '') or order.get('ご注文番号', '')
    material_name = order.get('資材名称', '') or order.get('発注資材名称', '')
    product_name = order.get('商品名', '')
    url = order.get('購入先URL', '')
    detail = order.get('色・サイズ等指定', '')
    lot_size = order.get('ロットサイズ', 1) or 1
    quantity = int(order.get('発注数', 0)) * int(lot_size)
    price = order.get('単価', 0)
    
    assert product_name, "商品名は必須です"
    assert url, "URLは必須です"
    assert quantity >= 0, f"数量は0以上である必要があります（商品: {product_name}）"
    
    if isinstance(price, str):
        try:
            price = float(price) if price else 0.0
        except ValueError:
            price = 0.0
    
    assert price >= 0, f"価格は0以上である必要があります（商品: {product_name}）"
    
    return PurchaseHistoryItem(
        purchase_date=purchase_date,
        order_number=str(order_number).strip(),
        material_name=str(material_name).strip(),
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
    assert credentials_file, "credentials_fileは必須です"
    assert order_groups is not None, "order_groupsはNoneであってはなりません"
    
    try:
        logger.info("[ステップ4] 購入履歴を記録しています...")
        base = BaseSheetsRepository(credentials_file)
        repository = SheetsPurchaseHistoryRepository(
            credentials_file=credentials_file,
            sheet_url=history_sheet_url,
            sheet_name=sheet_name or "使用資材",
            client=base.client,
        )
        total_recorded = 0
        for group in order_groups:
            for order in group:
                assert order is not None, "orderはNoneであってはなりません"
                try:
                    history_item = convert_order_to_history_item(order)
                    repository.append(history_item)
                    total_recorded += 1
                except Exception as e:
                    logger.warning(f"購入履歴の記録に失敗しました（商品: {order.get('商品名', '不明')}）: {e}")
                    continue
        
        assert total_recorded >= 0, "total_recordedは0以上である必要があります"
        logger.info(f"✓ {total_recorded}件の購入履歴を記録しました")
        
    except Exception as e:
        logger.error(f"購入履歴の記録中にエラーが発生しました: {e}")


