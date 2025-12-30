"""
購入履歴記録モジュール
"""

import logging
from datetime import datetime
from typing import List, Optional
from infrastructure.repositories import BaseSheetsRepository, SheetsPurchaseHistoryRepository
from domain.entities.order_group import OrderGroup
from domain.entities.order import Order
from domain.value_objects.purchase_history import PurchaseHistoryItem


logger = logging.getLogger(__name__)


def convert_order_to_history_item(order: Order, *, order_number: Optional[str] = None) -> PurchaseHistoryItem:
    assert order is not None, "orderはNoneであってはなりません"
    
    purchase_date = datetime.now().strftime('%Y-%m-%d')
    resolved_order_number = (order_number or "").strip()
    material_name = order.material_name
    product_name = order.product_name
    url = order.purchase_url
    detail = order.color_size_spec
    lot_size = int(order.lot_size or 1)
    quantity = int(order.order_quantity) * int(lot_size)
    price = order.unit_price if order.unit_price is not None else 0.0
    
    assert product_name, "商品名は必須です"
    assert url, "URLは必須です"
    assert quantity >= 0, f"数量は0以上である必要があります（商品: {product_name}）"
    
    assert price >= 0, f"価格は0以上である必要があります（商品: {product_name}）"
    
    return PurchaseHistoryItem(
        purchase_date=purchase_date,
        order_number=str(resolved_order_number).strip(),
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
    order_groups: List[OrderGroup],
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
        for result in order_groups:
            for order in result.order_group:
                assert order is not None, "orderはNoneであってはなりません"
                try:
                    history_item = convert_order_to_history_item(order, order_number=result.order_number or "")
                    repository.append(history_item)
                    total_recorded += 1
                except Exception as e:
                    logger.warning(f"購入履歴の記録に失敗しました（商品: {getattr(order, 'product_name', '不明')}）: {e}")
                    continue
        
        assert total_recorded >= 0, "total_recordedは0以上である必要があります"
        logger.info(f"✓ {total_recorded}件の購入履歴を記録しました")
        
    except Exception as e:
        logger.error(f"購入履歴の記録中にエラーが発生しました: {e}")


