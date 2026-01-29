from __future__ import annotations

import re
from typing import Any

from gspread.utils import rowcol_to_a1

from domain.value_objects.purchase_management import PurchaseManagementItem
from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository


def _extract_gid(sheet_url: str) -> int:
    match = re.search(r"[?&#]gid=(\d+)", sheet_url)
    if not match:
        raise ValueError("sheet_urlにgidがありません（例: ...?gid=123#gid=123）")
    return int(match.group(1))


class SheetsPurchaseManagementRepository(BaseSheetsRepository):
    """
    仕入管理シートへ追記するRepository。

    - worksheetはURLのgidで特定
    - ヘッダーは4行目
    - 4行目の列名を見てマッピングして追記
    """

    HEADER_ROW = 4

    @staticmethod
    def _to_sheet_number(value: float) -> int | float:
        """
        Google Sheetsへ数値として書き込むための整形。
        - 3.0 のような値は 3（int）で書く
        - 3.5 のような値は 3.5（float）で書く
        """
        v = float(value)
        return int(v) if v.is_integer() else v

    def __init__(self, credentials_file: str, sheet_url: str, sheet_name: str | None = None, client=None):
        super().__init__(credentials_file=credentials_file, client=client)
        self.sheet_url = sheet_url
        self.sheet_name = sheet_name

    @staticmethod
    def _find_last_filled_row_index(worksheet, *, start_row: int, key_col: int) -> int:
        """
        start_row 以降で「データが入っている最終行」を返す（見つからない場合は start_row - 1）。
        """
        if start_row > worksheet.row_count:
            return start_row - 1

        start_a1 = rowcol_to_a1(start_row, key_col)
        end_a1 = rowcol_to_a1(worksheet.row_count, key_col)
        values = worksheet.get(f"{start_a1}:{end_a1}")

        last_filled_offset = -1
        for idx, row in enumerate(values):
            cell_value = row[0] if row else ""
            if str(cell_value).strip() != "":
                last_filled_offset = idx

        return start_row + last_filled_offset

    @staticmethod
    def _choose_key_column(headers: list[str]) -> int:
        """
        追記先行を決めるために参照する列（1-based）を返す。
        可能なら注文番号/ASINを優先し、無ければ先頭列を使う。
        """
        header_cells = [str(h).strip() for h in headers]
        for i, name in enumerate(header_cells, start=1):
            if ("注文番号" in name) or ("発注番号" in name):
                return i
        for i, name in enumerate(header_cells, start=1):
            if "ASIN" in name:
                return i
        return 1

    @staticmethod
    def _contiguous_ranges(cols_0based: list[int]) -> list[tuple[int, int]]:
        """
        0-basedの列インデックス群を連続区間（[start, end_exclusive)）にまとめる。
        """
        if not cols_0based:
            return []
        cols_sorted = sorted(set(cols_0based))
        ranges: list[tuple[int, int]] = []
        start = cols_sorted[0]
        prev = cols_sorted[0]
        for c in cols_sorted[1:]:
            if c == prev + 1:
                prev = c
                continue
            ranges.append((start, prev + 1))
            start = c
            prev = c
        ranges.append((start, prev + 1))
        return ranges

    def append(self, item: PurchaseManagementItem) -> None:
        spreadsheet = self.client.open_by_url(self.sheet_url)
        worksheet = spreadsheet.worksheet(self.sheet_name)
        headers = worksheet.row_values(self.HEADER_ROW)
        if not headers:
            raise Exception("シートにヘッダーがありません（4行目にヘッダーが必要です）")

        value_by_header: dict[str, Any] = {
            "購入日": item.purchase_date,
            "注文日": item.purchase_date,
            "日付": item.purchase_date,
            "注文番号": item.order_number,
            "発注番号": item.order_number,
            "ASIN": item.asin,
            "商品名": item.product_name,
            # URLは「購入先」列にのみ入れる
            "購入先": item.url,
            "購入先URL": item.url,
            "購入先URLリンク": item.url,
            "画像": item.image_text,
            "備考": item.remark_text,
            "納品分類": item.delivery_category,
            "詳細": item.detail,
            "色": item.detail,
            "サイズ": item.detail,
            # 数値は文字列ではなく数値として書き込む（先頭に'が付いて文字扱いになるのを避ける）
            "数量": self._to_sheet_number(float(item.quantity)),
            "発注数": self._to_sheet_number(float(item.quantity)),
            "個数": self._to_sheet_number(float(item.quantity)),
            "購入数": self._to_sheet_number(float(item.quantity)),
            "通貨": "CNY",
            "通貨単位": "CNY",
            "単価": "" if item.unit_price is None else self._to_sheet_number(float(item.unit_price)),
            "価格": "" if item.unit_price is None else self._to_sheet_number(float(item.unit_price)),
            "金額": "" if item.total_price is None else self._to_sheet_number(float(item.total_price)),
            "合計": "" if item.total_price is None else self._to_sheet_number(float(item.total_price)),
            "資材": item.material_name,
            "資材名称": item.material_name,
        }

        header_cells = [str(h).strip() for h in headers]
        row_values: list[Any] = []
        for header_name in header_cells:
            matched: Any = ""
            for key, value in value_by_header.items():
                if key and key in header_name:
                    matched = value
                    break
            row_values.append(matched)

        # 追記対象の行を決める（append_rowは数式/フィルタの拡張と相性が悪いので、行番号を確定させて update する）
        start_row = self.HEADER_ROW + 1
        key_col = self._choose_key_column(headers)
        last_filled_row = self._find_last_filled_row_index(worksheet, start_row=start_row, key_col=key_col)
        target_row = last_filled_row + 1
        if target_row > worksheet.row_count:
            worksheet.add_rows(target_row - worksheet.row_count)

        start_a1 = rowcol_to_a1(target_row, 1)
        end_a1 = rowcol_to_a1(target_row, len(header_cells))
        worksheet.update(
            f"{start_a1}:{end_a1}",
            [row_values],
            value_input_option="USER_ENTERED",
        )

        # 直上行の数式をコピー（相対参照がズレないよう、copyPaste(=下方向コピー)で貼り付け）
        requests: list[dict[str, Any]] = []
        if target_row > start_row:
            prev_row = target_row - 1
            prev_start_a1 = rowcol_to_a1(prev_row, 1)
            prev_end_a1 = rowcol_to_a1(prev_row, len(header_cells))
            prev_row_values = worksheet.get(f"{prev_start_a1}:{prev_end_a1}", value_render_option="FORMULA")
            prev_cells = prev_row_values[0] if prev_row_values else []

            formula_cols_0based: list[int] = []
            for idx_0based, prev_cell in enumerate(prev_cells):
                is_formula = isinstance(prev_cell, str) and prev_cell.strip().startswith("=")
                is_empty_now = str(row_values[idx_0based]).strip() == ""
                if is_formula and is_empty_now:
                    formula_cols_0based.append(idx_0based)

            for start_col, end_col in self._contiguous_ranges(formula_cols_0based):
                requests.append(
                    {
                        "copyPaste": {
                            "source": {
                                "sheetId": worksheet.id,
                                "startRowIndex": prev_row - 1,
                                "endRowIndex": prev_row,
                                "startColumnIndex": start_col,
                                "endColumnIndex": end_col,
                            },
                            "destination": {
                                "sheetId": worksheet.id,
                                "startRowIndex": target_row - 1,
                                "endRowIndex": target_row,
                                "startColumnIndex": start_col,
                                "endColumnIndex": end_col,
                            },
                            "pasteType": "PASTE_FORMULA",
                            "pasteOrientation": "NORMAL",
                        }
                    }
                )

        # フィルタの範囲を自動拡張（basic filter / filter view）
        try:
            meta = spreadsheet.fetch_sheet_metadata()
            sheets = meta.get("sheets", [])
            sheet_meta = None
            for s in sheets:
                props = (s or {}).get("properties", {})
                if props.get("sheetId") == worksheet.id:
                    sheet_meta = s
                    break

            if sheet_meta:
                basic_filter = sheet_meta.get("basicFilter")
                if basic_filter and isinstance(basic_filter, dict):
                    bf_range = (basic_filter.get("range") or {}).copy()
                    end_row_idx = bf_range.get("endRowIndex")
                    # endRowIndex は 0-based exclusive。target_row は 1-based。
                    desired_end = max(int(end_row_idx or 0), int(target_row))
                    if end_row_idx is None or int(end_row_idx) < desired_end:
                        bf_range["endRowIndex"] = desired_end
                        new_filter = basic_filter.copy()
                        new_filter["range"] = bf_range
                        requests.append({"setBasicFilter": {"filter": new_filter}})

                filter_views = sheet_meta.get("filterViews") or []
                for view in filter_views:
                    if not isinstance(view, dict):
                        continue
                    view_range = (view.get("range") or {}).copy()
                    end_row_idx = view_range.get("endRowIndex")
                    desired_end = max(int(end_row_idx or 0), int(target_row))
                    if end_row_idx is None or int(end_row_idx) < desired_end:
                        view_range["endRowIndex"] = desired_end
                        new_view = view.copy()
                        new_view["range"] = view_range
                        requests.append(
                            {
                                "updateFilterView": {
                                    "filter": new_view,
                                    "fields": "range",
                                }
                            }
                        )
        except Exception:
            # フィルタが無い/取得できない環境でも、仕入管理の追記自体は成功させる
            pass

        if requests:
            spreadsheet.batch_update({"requests": requests})


