"""
仕入情報シートのValueObject
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class PurchaseInfoItem:
    asin: str
    title: str
    purchase_url: str
    color_size_spec: str
    quantity_per_item: int
    unit_price: float
    bulk_discounts: Dict[str, float]  # 数量割引情報（列名: 価格）
    chatwork_message: str = ""  # Chatwork文章
    chatwork_attachment: str = ""  # Chatwork添付
    
    def __post_init__(self):
        if not self.asin or not self.asin.strip():
            raise ValueError("ASINは必須です")
        if not self.title or not self.title.strip():
            raise ValueError("題名は必須です")
        if not self.purchase_url or not self.purchase_url.strip():
            raise ValueError("購入先URLは必須です")
        if self.quantity_per_item < 0:
            raise ValueError("1商品辺り発注数は0以上である必要があります")
        if self.unit_price < 0:
            raise ValueError("単価は0以上である必要があります")
    
    def get_best_price(self, order_quantity: int) -> float:
        import re

        # 基本単価をデフォルトとして設定
        best_price = self.unit_price if self.unit_price > 0 else float('inf')

        applicable_prices = []

        for col_name, price in self.bulk_discounts.items():
            if price <= 0:
                continue

            # 列名から最低数量を抽出
            match = re.search(r'(\d+)', str(col_name))
            if not match:
                continue

            min_quantity = float(match.group(1))

            # 発注数が最低数量以上の場合
            if order_quantity >= min_quantity:
                applicable_prices.append((min_quantity, price))

        # 適用可能な価格がある場合、最も安い価格を選択
        if applicable_prices:
            applicable_prices.sort(key=lambda x: x[1])  # 価格でソート
            cheapest_discount_price = applicable_prices[0][1]
            # 基本単価よりも安い場合のみ数量割引価格を使用
            if cheapest_discount_price < best_price:
                best_price = cheapest_discount_price

        # best_priceがinfの場合は0を返す
        if best_price == float('inf'):
            best_price = 0.0

        return best_price


class PurchaseInfoSheet:
    def __init__(self, items: List[PurchaseInfoItem]):
        self._items = tuple(items)  # イミュータブルにするためtupleに変換
    
    @property
    def items(self) -> List[PurchaseInfoItem]:
        return list(self._items)
    
    @property
    def asins(self) -> List[str]:
        return [item.asin for item in self._items]
    
    def get_by_asin(self, asin: str) -> List[PurchaseInfoItem]:
        return [item for item in self._items if item.asin == asin]
    
    def to_dataframe(self) -> pd.DataFrame:
        data = {
            'ASIN': [item.asin for item in self._items],
            '購入先URL': [item.purchase_url for item in self._items],
            '題名': [item.title for item in self._items],
            '色・サイズ等指定': [item.color_size_spec for item in self._items],
            '1商品辺り発注数': [item.quantity_per_item for item in self._items],
            '単価': [item.unit_price for item in self._items],
            'chatwork文章': [item.chatwork_message for item in self._items],
            'chatwork添付': [item.chatwork_attachment for item in self._items]
        }
        
        # すべての数量割引列名を収集
        all_bulk_discount_cols = set()
        for item in self._items:
            all_bulk_discount_cols.update(item.bulk_discounts.keys())
        
        # 数量割引列を初期化（Noneで埋める）
        for col_name in all_bulk_discount_cols:
            data[col_name] = [None] * len(self._items)
        
        # DataFrameを作成
        df = pd.DataFrame(data)
        
        # 数量割引情報を設定
        for idx, item in enumerate(self._items):
            for col_name, price in item.bulk_discounts.items():
                df.at[idx, col_name] = price
        
        return df
    
    @classmethod
    def _create_item_from_row(cls, row: pd.Series, bulk_discount_columns: List[str]) -> Optional[PurchaseInfoItem]:
        asin = str(row['ASIN']).strip()
        if not asin:  # 空行はスキップ
            return None
        
        title = str(row['題名']).strip()
        purchase_url = str(row['購入先URL']).strip()
        color_size_spec = str(row['色・サイズ等指定']).strip() if pd.notna(row['色・サイズ等指定']) else ''
        quantity_per_item = int(row['1商品辺り発注数']) if pd.notna(row['1商品辺り発注数']) else 0
        unit_price = float(row['単価']) if pd.notna(row['単価']) else 0.0
        
        # Chatwork情報を取得
        chatwork_message = str(row['chatwork文章']).strip() if 'chatwork文章' in row.index and pd.notna(row.get('chatwork文章')) else ''
        chatwork_attachment = str(row['chatwork添付']).strip() if 'chatwork添付' in row.index and pd.notna(row.get('chatwork添付')) else ''
        
        # 数量割引情報を取得
        bulk_discounts = {}
        for col_name in bulk_discount_columns:
            if col_name in row.index and pd.notna(row[col_name]):
                price = float(row[col_name])
                if price > 0:
                    bulk_discounts[col_name] = price
        
        return PurchaseInfoItem(
            asin=asin,
            title=title,
            purchase_url=purchase_url,
            color_size_spec=color_size_spec,
            quantity_per_item=quantity_per_item,
            unit_price=unit_price,
            bulk_discounts=bulk_discounts,
            chatwork_message=chatwork_message,
            chatwork_attachment=chatwork_attachment
        )
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> 'PurchaseInfoSheet':
        items = []
        
        # 基本列名
        base_columns = ['ASIN', '購入先URL', '題名', '色・サイズ等指定', '1商品辺り発注数', '単価', 'chatwork文章', 'chatwork添付']
        
        # 数量割引列を特定（基本列以外）
        bulk_discount_columns = [col for col in df.columns if col not in base_columns]
        
        for _, row in df.iterrows():
            item = cls._create_item_from_row(row, bulk_discount_columns)
            if item:
                items.append(item)
        
        return cls(items=items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __repr__(self) -> str:
        return f"PurchaseInfoSheet(items={len(self._items)})"



