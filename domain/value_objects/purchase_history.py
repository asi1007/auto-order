"""
購入履歴のValueObject
"""

import pandas as pd
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PurchaseHistoryItem:
    purchase_date: str
    product_name: str
    url: str
    detail: str
    quantity: int
    price: float
    
    def __post_init__(self):
        if not self.product_name or not self.product_name.strip():
            raise ValueError("商品名は必須です")
        if not self.url or not self.url.strip():
            raise ValueError("URLは必須です")
        if self.quantity < 0:
            raise ValueError("数量は0以上である必要があります")
        if self.price < 0:
            raise ValueError("価格は0以上である必要があります")


class PurchaseHistorySheet:
    def __init__(self, items: List[PurchaseHistoryItem]):
        self._items = tuple(items)
    
    @property
    def items(self) -> List[PurchaseHistoryItem]:
        return list(self._items)
    
    def to_dataframe(self) -> pd.DataFrame:
        data = {
            '購入日': [item.purchase_date for item in self._items],
            '商品名': [item.product_name for item in self._items],
            'URL': [item.url for item in self._items],
            '詳細': [item.detail for item in self._items],
            '数量': [item.quantity for item in self._items],
            '価格': [item.price for item in self._items]
        }
        return pd.DataFrame(data)
    
    @classmethod
    def _create_item_from_row(cls, row: pd.Series, purchase_date_col: str, product_name_col: str,
                              url_col: str, detail_col: str, quantity_col: str, price_col: str) -> Optional[PurchaseHistoryItem]:
        purchase_date = str(row[purchase_date_col]).strip() if purchase_date_col and purchase_date_col in row.index and pd.notna(row.get(purchase_date_col)) else ''
        product_name = str(row[product_name_col]).strip() if product_name_col and product_name_col in row.index and pd.notna(row.get(product_name_col)) else ''
        url = str(row[url_col]).strip() if url_col and url_col in row.index and pd.notna(row.get(url_col)) else ''
        detail = str(row[detail_col]).strip() if detail_col and detail_col in row.index and pd.notna(row.get(detail_col)) else ''
        
        if not product_name or not url:
            return None
        
        quantity = int(row[quantity_col]) if quantity_col and quantity_col in row.index and pd.notna(row.get(quantity_col)) else 0
        price = float(row[price_col]) if price_col and price_col in row.index and pd.notna(row.get(price_col)) else 0.0
        
        if not purchase_date:
            purchase_date = datetime.now().strftime('%Y-%m-%d')
        
        return PurchaseHistoryItem(
            purchase_date=purchase_date,
            product_name=product_name,
            url=url,
            detail=detail,
            quantity=quantity,
            price=price
        )
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, purchase_date_col: str, product_name_col: str,
                       url_col: str, detail_col: str, quantity_col: str, price_col: str) -> 'PurchaseHistorySheet':
        items = []
        
        for _, row in df.iterrows():
            item = cls._create_item_from_row(row, purchase_date_col, product_name_col, url_col, detail_col, quantity_col, price_col)
            if item:
                items.append(item)
        
        return cls(items=items)
    
    def add_history(self, item: PurchaseHistoryItem) -> 'PurchaseHistorySheet':
        new_items = list(self._items) + [item]
        return PurchaseHistorySheet(items=new_items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __repr__(self) -> str:
        return f"PurchaseHistorySheet(items={len(self._items)})"

