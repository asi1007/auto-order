"""
売上シートのValueObject
"""

import pandas as pd
from typing import List
from dataclasses import dataclass


@dataclass(frozen=True)
class SalesItem:
    asin: str
    order_quantity: int
    product_name: str = ""
    image_text: str = ""
    remark_text: str = ""
    delivery_category: str = ""
    
    def __post_init__(self):
        if not self.asin or not self.asin.strip():
            raise ValueError("ASINは必須です")
        if self.order_quantity < 0:
            raise ValueError("発注数は0以上である必要があります")


class SalesSheet:
    def __init__(self, items: List[SalesItem]):
        self._items = tuple(items)  # イミュータブルにするためtupleに変換
    
    @property
    def items(self) -> List[SalesItem]:
        return list(self._items)
    
    @property
    def asins(self) -> List[str]:
        return [item.asin for item in self._items]
    
    def get_order_quantity(self, asin: str) -> int:
        for item in self._items:
            if item.asin == asin:
                return item.order_quantity
        return 0
    
    def to_dataframe(self) -> pd.DataFrame:
        data = {
            'ASIN': [item.asin for item in self._items],
            '商品名': [item.product_name for item in self._items],
            '画像': [item.image_text for item in self._items],
            '備考': [item.remark_text for item in self._items],
            '納品分類': [item.delivery_category for item in self._items],
            '発注数': [item.order_quantity for item in self._items],
        }
        return pd.DataFrame(data)
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> 'SalesSheet':
        items = []
        for _, row in df.iterrows():
            asin = str(row['ASIN']).strip()
            qty_raw = row.get('発注数')
            qty = pd.to_numeric(qty_raw, errors="coerce")
            if pd.isna(qty):
                # 発注数が数値に変換できない行はスキップ
                continue
            order_quantity = int(qty)
            product_name = str(row['商品名']).strip() if '商品名' in df.columns and pd.notna(row.get('商品名')) else ""
            image_text = str(row['画像']).strip() if '画像' in df.columns and pd.notna(row.get('画像')) else ""
            remark_text = str(row['備考']).strip() if '備考' in df.columns and pd.notna(row.get('備考')) else ""
            delivery_category = str(row['納品分類']).strip() if '納品分類' in df.columns and pd.notna(row.get('納品分類')) else ""
            if asin:  # 空行はスキップ
                items.append(
                    SalesItem(
                        asin=asin,
                        order_quantity=order_quantity,
                        product_name=product_name,
                        image_text=image_text,
                        remark_text=remark_text,
                        delivery_category=delivery_category,
                    )
                )
        return cls(items=items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __repr__(self) -> str:
        return f"SalesSheet(items={len(self._items)})"



