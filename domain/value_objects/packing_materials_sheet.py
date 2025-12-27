"""
梱包材シートのValueObject
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class PackingMaterialsItem:
    url: str
    product_name: str
    detail: str
    price: float
    order_quantity: int
    
    def __post_init__(self):
        if not self.url or not self.url.strip():
            raise ValueError("URLは必須です")
        if not self.product_name or not self.product_name.strip():
            raise ValueError("商品名は必須です")
        if self.price < 0:
            raise ValueError("価格は0以上である必要があります")
        if self.order_quantity < 0:
            raise ValueError("発注数は0以上である必要があります")


class PackingMaterialsSheet:
    def __init__(self, items: List[PackingMaterialsItem]):
        self._items = tuple(items)
    
    @property
    def items(self) -> List[PackingMaterialsItem]:
        return list(self._items)
    
    def to_dataframe(self) -> pd.DataFrame:
        data = {
            'url': [item.url for item in self._items],
            '商品名': [item.product_name for item in self._items],
            '詳細': [item.detail for item in self._items],
            '価格': [item.price for item in self._items],
            '発注数': [item.order_quantity for item in self._items]
        }
        return pd.DataFrame(data)
    
    @classmethod
    def _create_item_from_row(cls, row: pd.Series, url_col: str, product_name_col: str, 
                              detail_col: str, price_col: str, order_quantity_col: str) -> Optional[PackingMaterialsItem]:
        url = str(row[url_col]).strip() if url_col and url_col in row.index and pd.notna(row.get(url_col)) else ''
        product_name = str(row[product_name_col]).strip() if product_name_col and product_name_col in row.index and pd.notna(row.get(product_name_col)) else ''
        detail = str(row[detail_col]).strip() if detail_col and detail_col in row.index and pd.notna(row.get(detail_col)) else ''
        
        if not url or not product_name:
            return None
        
        price = float(row[price_col]) if price_col and price_col in row.index and pd.notna(row.get(price_col)) else 0.0
        order_quantity = int(row[order_quantity_col]) if order_quantity_col and order_quantity_col in row.index and pd.notna(row.get(order_quantity_col)) else 0
        
        return PackingMaterialsItem(
            url=url,
            product_name=product_name,
            detail=detail,
            price=price,
            order_quantity=order_quantity
        )
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, url_col: str, product_name_col: str, 
                       detail_col: str, price_col: str, order_quantity_col: str) -> 'PackingMaterialsSheet':
        items = []
        
        for _, row in df.iterrows():
            item = cls._create_item_from_row(row, url_col, product_name_col, detail_col, price_col, order_quantity_col)
            if item:
                items.append(item)
        
        return cls(items=items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __repr__(self) -> str:
        return f"PackingMaterialsSheet(items={len(self._items)})"

