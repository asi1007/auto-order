from __future__ import annotations

import pandas as pd

from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository
from domain.value_objects.sales_sheet import SalesSheet


class SheetsSalesSheetRepository(BaseSheetsRepository):
    def read(self, sheet_url: str, sheet_name: str = "売上/日") -> SalesSheet:
        worksheet = self.open_worksheet(sheet_url, sheet_name)
        data = worksheet.get_all_values()

        if len(data) < 3:
            raise Exception("シートにデータがありません（列名は2行目、データは3行目以降が必要です）")

        df = pd.DataFrame(data[2:], columns=data[1])
        if len(df.columns) < 2:
            raise Exception(f"シートの列数が不足しています。必要: 2列以上, 実際: {len(df.columns)}列")

        # ヘッダー名から列を特定（無ければ従来通り先頭列を使う）
        col_asin = None
        col_qty = None
        col_name = None
        col_image = None
        for col in df.columns:
            col_str = str(col).strip()
            if col_asin is None and "ASIN" in col_str:
                col_asin = col
            if col_qty is None and ("発注数" in col_str or "注文数" in col_str):
                col_qty = col
            if col_name is None and ("商品名" in col_str or "題名" in col_str):
                col_name = col
            if col_image is None and "画像" in col_str:
                col_image = col

        if col_asin is None:
            col_asin = df.columns[0]
        if col_qty is None:
            col_qty = df.columns[1]

        columns = {"ASIN": col_asin, "発注数": col_qty}
        if col_name is not None:
            columns["商品名"] = col_name
        if col_image is not None:
            columns["画像"] = col_image

        df_filtered = df[list(columns.values())].copy()
        df_filtered.columns = list(columns.keys())

        df_filtered = df_filtered[df_filtered["ASIN"].astype(str).str.strip() != ""]
        df_filtered["発注数"] = pd.to_numeric(df_filtered["発注数"], errors="coerce")
        df_filtered = df_filtered.dropna()

        return SalesSheet.from_dataframe(df_filtered)

