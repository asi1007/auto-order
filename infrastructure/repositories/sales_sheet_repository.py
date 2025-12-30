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

        df_filtered = df.iloc[:, [0, 1]].copy()
        df_filtered.columns = ["ASIN", "発注数"]

        df_filtered = df_filtered[df_filtered["ASIN"].astype(str).str.strip() != ""]
        df_filtered["発注数"] = pd.to_numeric(df_filtered["発注数"], errors="coerce")
        df_filtered = df_filtered.dropna()

        return SalesSheet.from_dataframe(df_filtered)

