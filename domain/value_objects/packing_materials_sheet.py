"""
梱包材シートのValueObject
"""

from __future__ import annotations

import pandas as pd
from typing import List, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    import gspread

@dataclass(frozen=True)
class PackingMaterialsItem:
    material_name: str
    url: str
    product_name: str
    detail: str
    price: float
    order_quantity: int
    lot_size: int
    
    def __post_init__(self):
        if not self.material_name or not self.material_name.strip():
            raise ValueError("資材名称は必須です")
        if not self.url or not self.url.strip():
            raise ValueError("URLは必須です")
        if not self.product_name or not self.product_name.strip():
            raise ValueError("商品名は必須です")
        if self.price < 0:
            raise ValueError("価格は0以上である必要があります")
        if self.order_quantity < 0:
            raise ValueError("発注数は0以上である必要があります")
        if self.lot_size <= 0:
            raise ValueError("ロットサイズは1以上である必要があります")


class PackingMaterialsSheet:
    def __init__(self, items: List[PackingMaterialsItem]):
        self._items = tuple(items)

     
    @property
    def items(self) -> List[PackingMaterialsItem]:
        return list(self._items)
    
    def to_dataframe(self) -> pd.DataFrame:
        data = {
            '資材名称': [item.material_name for item in self._items],
            'url': [item.url for item in self._items],
            '商品名': [item.product_name for item in self._items],
            '詳細': [item.detail for item in self._items],
            '価格': [item.price for item in self._items],
            '発注数': [item.order_quantity for item in self._items],
            'ロットサイズ': [item.lot_size for item in self._items],
        }
        return pd.DataFrame(data)
    
    @classmethod
    def _normalize_cell_value(cls, value):
        if isinstance(value, pd.Series):
            value = value.iloc[0] if len(value) > 0 else ""
        return value

    @classmethod
    def _create_item_from_row(cls, row: pd.Series, url_col: str, product_name_col: str, 
                              detail_col: str, price_col: str, order_quantity_col: str,
                              material_name_col: str, lot_size_col: str) -> Optional[PackingMaterialsItem]:
        raw_material_name = cls._normalize_cell_value(row.get(material_name_col, "")) if material_name_col else ""
        raw_url = cls._normalize_cell_value(row.get(url_col, "")) if url_col else ""
        raw_product_name = cls._normalize_cell_value(row.get(product_name_col, "")) if product_name_col else ""
        raw_detail = cls._normalize_cell_value(row.get(detail_col, "")) if detail_col else ""

        material_name = "" if pd.isna(raw_material_name) else str(raw_material_name).strip()
        url = "" if pd.isna(raw_url) else str(raw_url).strip()
        product_name = "" if pd.isna(raw_product_name) else str(raw_product_name).strip()
        detail = "" if pd.isna(raw_detail) else str(raw_detail).strip()
        
        if not material_name or not url or not product_name:
            return None
        
        raw_price = cls._normalize_cell_value(row.get(price_col, 0)) if price_col else 0
        raw_order_quantity = cls._normalize_cell_value(row.get(order_quantity_col, 0)) if order_quantity_col else 0
        raw_lot_size = cls._normalize_cell_value(row.get(lot_size_col, 1)) if lot_size_col else 1

        price = 0.0 if pd.isna(raw_price) else float(raw_price) if str(raw_price).strip() != "" else 0.0
        order_quantity = 0 if pd.isna(raw_order_quantity) else int(float(raw_order_quantity)) if str(raw_order_quantity).strip() != "" else 0
        lot_size = 1 if pd.isna(raw_lot_size) else int(float(raw_lot_size)) if str(raw_lot_size).strip() != "" else 1
        
        return PackingMaterialsItem(
            material_name=material_name,
            url=url,
            product_name=product_name,
            detail=detail,
            price=price,
            order_quantity=order_quantity
            ,lot_size=lot_size
        )
    
    @classmethod
    def from_sheet(
        cls,
        sheet: "gspread.Worksheet",
        header_row_index: int = 2,
    ) -> "PackingMaterialsSheet":
        data = sheet.get_all_values()
        assert len(data) >= header_row_index, "ヘッダー行が存在しません"
        headers = data[header_row_index - 1]
        rows = data[header_row_index:]
        normalized_headers = [str(h).strip() for h in headers]

        duplicates: dict[str, List[int]] = {}
        for idx, name in enumerate(normalized_headers, start=1):
            if not name:
                continue
            duplicates.setdefault(name, []).append(idx)
        duplicated_items = {k: v for k, v in duplicates.items() if len(v) >= 2}
        if duplicated_items:
            details = ", ".join([f"{k}({v})" for k, v in duplicated_items.items()])
            raise Exception(f"ヘッダー行に重複列があります: {details}")

        df = pd.DataFrame(rows, columns=normalized_headers)

        required_headers = ["資材名称", "発注数", "ロットサイズ", "URL", "商品名", "詳細", "価格"]
        missing = [h for h in required_headers if h not in df.columns]
        assert not missing, f"必要なヘッダーが不足しています: {sorted(missing)}"

        df_filtered = df[required_headers].copy()

        material_name_col = "資材名称"
        order_quantity_col = "発注数"
        lot_size_col = "ロットサイズ"
        url_col = "URL"
        product_name_col = "商品名"
        detail_col = "詳細"
        price_col = "価格"

        return cls.from_dataframe(
            df_filtered,
            url_col,
            product_name_col,
            detail_col,
            price_col,
            order_quantity_col,
            material_name_col,
            lot_size_col,
        )
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, url_col: str, product_name_col: str, 
                       detail_col: str, price_col: str, order_quantity_col: str,
                       material_name_col: str, lot_size_col: str) -> 'PackingMaterialsSheet':
        items = []
        
        for _, row in df.iterrows():
            item = cls._create_item_from_row(
                row,
                url_col,
                product_name_col,
                detail_col,
                price_col,
                order_quantity_col,
                material_name_col,
                lot_size_col,
            )
            if item:
                items.append(item)
        
        return cls(items=items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __repr__(self) -> str:
        return f"PackingMaterialsSheet(items={len(self._items)})"


