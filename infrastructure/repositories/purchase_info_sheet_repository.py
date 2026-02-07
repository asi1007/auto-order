from __future__ import annotations

import pandas as pd

from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository
from domain.value_objects.purchase_info_sheet import PurchaseInfoSheet


class SheetsPurchaseInfoSheetRepository(BaseSheetsRepository):
    def read_selling_prices(self, sheet_url: str, sheet_name: str = "納品状況") -> dict[str, float]:
        """
        納品状況シートから ASIN → 販売価格 の辞書を返す。
        1行目ヘッダー、A列=ASIN、「販売価格」列（ヘッダー名で検出）。
        """
        worksheet = self.open_worksheet(sheet_url, sheet_name)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return {}

        headers = [str(h).strip() for h in data[0]]
        asin_col: int | None = None
        price_col: int | None = None
        for i, h in enumerate(headers):
            if "ASIN" in h and asin_col is None:
                asin_col = i
            if "販売価格" in h and price_col is None:
                price_col = i
        if asin_col is None or price_col is None:
            return {}

        result: dict[str, float] = {}
        for row in data[1:]:
            asin = str(row[asin_col]).strip() if asin_col < len(row) else ""
            price_str = str(row[price_col]).strip() if price_col < len(row) else ""
            if not asin or not price_str:
                continue
            try:
                result[asin] = float(price_str)
            except ValueError:
                continue
        return result

    def read(self, sheet_url: str, sheet_name: str = "仕入情報") -> PurchaseInfoSheet:
        worksheet = self.open_worksheet(sheet_url, sheet_name)
        data = worksheet.get_all_values()

        if len(data) < 3:
            raise Exception("シートにデータがありません（列名は2行目、データは3行目以降が必要です）")

        df = pd.DataFrame(data[2:], columns=data[1])
        if len(df.columns) < 12:
            raise Exception(f"シートの列数が不足しています。必要: 12列以上, 実際: {len(df.columns)}列")

        required_columns = [0, 3, 4, 5, 6, 11]
        df_filtered = df.iloc[:, required_columns].copy()
        df_filtered.columns = ["ASIN", "購入先URL", "題名", "色・サイズ等指定", "1商品辺り発注数", "単価"]

        chatwork_message_col = None
        chatwork_attachment_col = None
        for idx, col_name in enumerate(df.columns):
            col_name_lower = str(col_name).lower()
            if "chatwork" in col_name_lower and ("文章" in str(col_name) or "message" in col_name_lower):
                chatwork_message_col = idx
            elif "chatwork" in col_name_lower and ("添付" in str(col_name) or "attachment" in col_name_lower):
                chatwork_attachment_col = idx

        df_filtered["chatwork文章"] = df.iloc[:, chatwork_message_col].values if chatwork_message_col is not None else ""
        df_filtered["chatwork添付"] = df.iloc[:, chatwork_attachment_col].values if chatwork_attachment_col is not None else ""

        if len(df.columns) >= 26:
            excluded = set(required_columns)
            if chatwork_message_col is not None:
                excluded.add(chatwork_message_col)
            if chatwork_attachment_col is not None:
                excluded.add(chatwork_attachment_col)

            for col_idx in range(12, 26):
                if col_idx in excluded:
                    continue
                col_name = df.columns[col_idx]
                df_filtered[col_name] = df.iloc[:, col_idx].values

        df_filtered = df_filtered[df_filtered["ASIN"].astype(str).str.strip() != ""]
        df_filtered["1商品辺り発注数"] = pd.to_numeric(df_filtered["1商品辺り発注数"], errors="coerce")
        df_filtered["単価"] = pd.to_numeric(df_filtered["単価"], errors="coerce")

        if len(df.columns) >= 26:
            for col_idx in range(12, 26):
                col_name = df.columns[col_idx]
                if col_name in df_filtered.columns:
                    df_filtered[col_name] = pd.to_numeric(df_filtered[col_name], errors="coerce")

        df_filtered = df_filtered.dropna(subset=["ASIN", "題名", "購入先URL"])
        return PurchaseInfoSheet.from_dataframe(df_filtered)

