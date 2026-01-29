from __future__ import annotations

import pandas as pd
from gspread.utils import rowcol_to_a1

from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository
from domain.value_objects.sales_sheet import SalesSheet


class SheetsSalesSheetRepository(BaseSheetsRepository):
    @staticmethod
    def _find_header_row_index(data: list[list[str]]) -> int:
        # ヘッダー行を自動検出（ASIN + 発注数/注文数 がある行）
        for idx, row in enumerate(data):
            row_str = [str(c).strip() for c in row]
            has_asin = any("ASIN" in c for c in row_str)
            has_qty = any(("発注数" in c) or ("注文数" in c) for c in row_str)
            if has_asin and has_qty:
                return idx
        raise Exception("シートにデータがありません（ヘッダー行/データ行が見つかりません）")

    @staticmethod
    def _find_asin_and_qty_column_indices(header_row: list[str]) -> tuple[int, int]:
        idx_asin: int | None = None
        idx_qty: int | None = None
        for i, col in enumerate(header_row):
            col_str = str(col).strip()
            if idx_asin is None and "ASIN" in col_str:
                idx_asin = i
            if idx_qty is None and ("発注数" in col_str or "注文数" in col_str):
                idx_qty = i
        if idx_asin is None:
            idx_asin = 0
        if idx_qty is None:
            if len(header_row) < 2:
                raise Exception("シートの列数が不足しています（ASIN/発注数の列が見つかりません）")
            idx_qty = 1
        return int(idx_asin), int(idx_qty)

    @staticmethod
    def _contiguous_ranges(rows_1based: list[int]) -> list[tuple[int, int]]:
        """
        1-based行番号のリストを連続区間（[start, end_inclusive]）にまとめる。
        """
        if not rows_1based:
            return []
        rows_sorted = sorted(set(int(r) for r in rows_1based))
        ranges: list[tuple[int, int]] = []
        start = rows_sorted[0]
        prev = rows_sorted[0]
        for r in rows_sorted[1:]:
            if r == prev + 1:
                prev = r
                continue
            ranges.append((start, prev))
            start = r
            prev = r
        ranges.append((start, prev))
        return ranges

    def read(self, sheet_url: str, sheet_name: str = "売上/日") -> SalesSheet:
        worksheet = self.open_worksheet(sheet_url, sheet_name)
        # 画像列は `=IMAGE(...)` 等の数式が入る想定なので、値ではなく数式を取得する
        data = worksheet.get_all_values(value_render_option="FORMULA")
        if not data or len(data) < 2:
            raise Exception("シートにデータがありません（ヘッダー行が見つかりません）")

        header_idx = self._find_header_row_index(data)
        if header_idx >= len(data) - 1:
            raise Exception("シートにデータがありません（ヘッダー行/データ行が見つかりません）")

        df = pd.DataFrame(data[header_idx + 1 :], columns=data[header_idx])
        if df.empty:
            raise Exception("シートにデータがありません（データ行がありません）")

        # ヘッダー名から列を特定（無ければ従来通り先頭列を使う）
        col_asin = None
        col_qty = None
        col_name = None
        col_image = None
        col_remark = None
        col_delivery_category = None
        idx_asin: int | None = None
        idx_qty: int | None = None
        idx_name: int | None = None
        idx_image: int | None = None
        idx_remark: int | None = None
        idx_delivery_category: int | None = None
        for i, col in enumerate(df.columns):
            col_str = str(col).strip()
            if col_asin is None and "ASIN" in col_str:
                col_asin = col
                idx_asin = i
            if col_qty is None and ("発注数" in col_str or "注文数" in col_str):
                col_qty = col
                idx_qty = i
            if col_name is None and ("商品名" in col_str or "題名" in col_str):
                col_name = col
                idx_name = i
            if col_image is None and "画像" in col_str:
                col_image = col
                idx_image = i
            if col_remark is None and "備考" in col_str:
                col_remark = col
                idx_remark = i
            if col_delivery_category is None and "納品分類" in col_str:
                col_delivery_category = col
                idx_delivery_category = i

        if col_asin is None:
            col_asin = df.columns[0]
            idx_asin = 0
        if col_qty is None:
            # 発注数列が見つからない場合でも、最低限2列あることを期待する
            if len(df.columns) < 2:
                raise Exception("シートの列数が不足しています（ASIN/発注数の列が見つかりません）")
            col_qty = df.columns[1]
            idx_qty = 1

        # NOTE: df.columns に同名がある場合、df[label] は複数列返すため
        # 「列名」ではなく「列インデックス」で選択して1列に確定させる
        selected_keys: list[str] = ["ASIN", "発注数"]
        selected_indices: list[int] = [int(idx_asin), int(idx_qty)]
        if idx_name is not None:
            selected_keys.append("商品名")
            selected_indices.append(int(idx_name))
        if idx_image is not None:
            selected_keys.append("画像")
            selected_indices.append(int(idx_image))
        if idx_remark is not None:
            selected_keys.append("備考")
            selected_indices.append(int(idx_remark))
        if idx_delivery_category is not None:
            selected_keys.append("納品分類")
            selected_indices.append(int(idx_delivery_category))

        df_filtered = df.iloc[:, selected_indices].copy()
        df_filtered.columns = selected_keys
        df_filtered = df_filtered[df_filtered["ASIN"].astype(str).str.strip() != ""]

        return SalesSheet.from_dataframe(df_filtered)

    def clear_order_quantities(self, sheet_url: str, asins: list[str], sheet_name: str = "売上/日") -> int:
        """
        発注完了したASINの「発注数（注文数）」セルを空欄に戻す。
        失敗したASINは呼び出し側で除外することを想定。

        戻り値: 空欄にした行数
        """
        if not asins:
            return 0

        worksheet = self.open_worksheet(sheet_url, sheet_name)
        data = worksheet.get_all_values(value_render_option="FORMULA")
        if not data or len(data) < 2:
            raise Exception("シートにデータがありません（ヘッダー行が見つかりません）")

        header_idx = self._find_header_row_index(data)
        header_row = data[header_idx]
        idx_asin, idx_qty = self._find_asin_and_qty_column_indices(header_row)

        target_asins = {str(a).strip() for a in asins if str(a).strip()}
        if not target_asins:
            return 0

        # data行の開始: header_idxの次の行。シート上の行番号は 1-based なので +2
        start_row_1based = header_idx + 2
        rows_to_clear: list[int] = []
        for offset, row in enumerate(data[header_idx + 1 :], start=start_row_1based):
            asin_value = ""
            if idx_asin < len(row):
                asin_value = str(row[idx_asin]).strip()
            if asin_value in target_asins:
                rows_to_clear.append(int(offset))

        if not rows_to_clear:
            return 0

        # 発注数列（1-based列番号）をまとめて空欄更新
        qty_col_1based = idx_qty + 1
        for start_row, end_row in self._contiguous_ranges(rows_to_clear):
            start_a1 = rowcol_to_a1(start_row, qty_col_1based)
            end_a1 = rowcol_to_a1(end_row, qty_col_1based)
            values = [[""] for _ in range(end_row - start_row + 1)]
            worksheet.update(f"{start_a1}:{end_a1}", values, value_input_option="USER_ENTERED")

        return len(set(rows_to_clear))

