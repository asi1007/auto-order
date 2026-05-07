from __future__ import annotations

import logging
import re
from typing import Any

from gspread.utils import rowcol_to_a1

from domain.value_objects.purchase_management import PurchaseManagementItem
from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository


logger = logging.getLogger(__name__)


def _extract_gid(sheet_url: str) -> int:
    match = re.search(r"[?&#]gid=(\d+)", sheet_url)
    if not match:
        raise ValueError("sheet_urlにgidがありません（例: ...?gid=123#gid=123）")
    return int(match.group(1))


class SheetsPurchaseManagementRepository(BaseSheetsRepository):
    HEADER_ROW = 4

    FORMULA_ONLY_COLUMNS: set[str] = {
        "買付完了日",
        "到着日",
        "状態",
        "昨日売上個数",
        "３日平均売上個数",
        "3日平均売上個数",
        "週平均売上個数",
        "合計日数",
        "FBA日数",
        "手配中在庫日数",
        "FBA在庫",
        "未発送+梱包依頼済み+納品中",
        "イーウーステータス",
        "年",
        "月",
        "週",
        "行番号",
    }

    NEVER_COPY_FORMULA_COLUMNS: set[str] = {
        "プラン別名",
    }

    def __init__(self, credentials_file: str, sheet_url: str, sheet_name: str | None = None, client=None):
        super().__init__(credentials_file=credentials_file, client=client)
        self.sheet_url = sheet_url
        self.sheet_name = sheet_name
        self._spreadsheet = self.client.open_by_url(self.sheet_url)
        self._worksheet = self._spreadsheet.worksheet(self.sheet_name)
        headers = self._worksheet.row_values(self.HEADER_ROW)
        if not headers:
            raise Exception("シートにヘッダーがありません（4行目にヘッダーが必要です）")
        self._header_cells = [str(h).strip() for h in headers]

    def append(self, item: PurchaseManagementItem) -> None:
        header_cells = self._header_cells
        row_values = self._build_row_values(item, header_cells)
        target_row = self._determine_target_row(self._worksheet, header_cells)

        # フィルタを一時解除（フィルタ適用中のcopyPasteエラーを回避）
        saved_filter = self._clear_basic_filter(self._spreadsheet, self._worksheet)

        self._write_row(self._worksheet, target_row, header_cells, row_values)

        # 直前の行から数式をコピー
        formula_requests = self._build_formula_copy_requests(self._worksheet, target_row, header_cells, row_values)
        if formula_requests:
            self._execute_batch_update(self._spreadsheet, formula_requests)

        # フィルタを復元（範囲を新しい行まで拡張して再適用）
        self._restore_basic_filter(self._spreadsheet, self._worksheet, saved_filter, target_row)

        # フィルタビューの範囲を拡張
        filter_view_requests = self._build_filter_view_expand_requests(self._spreadsheet, self._worksheet, target_row)
        if filter_view_requests:
            self._execute_batch_update(self._spreadsheet, filter_view_requests)

    def _build_row_values(self, item: PurchaseManagementItem, header_cells: list[str]) -> list[Any]:
        value_by_header = self._create_value_mapping(item)
        row_values: list[Any] = []
        for header_name in header_cells:
            matched = self._find_matching_value(header_name, value_by_header)
            row_values.append(matched)
        return row_values

    def _create_value_mapping(self, item: PurchaseManagementItem) -> dict[str, Any]:
        return {
            "購入日": item.purchase_date,
            "注文番号": item.order_number,
            "ASIN": item.asin,
            "商品名": item.product_name,
            "購入先": item.url,
            "画像": item.image_text,
            "備考": item.remark_text,
            "納品分類": item.delivery_category,
            "購入数": self._to_sheet_number(float(item.quantity)),
            "通貨": "CNY",
            "現地価格": "" if item.unit_price is None else self._to_sheet_number(float(item.unit_price)),
            "購入価格": "" if item.unit_price_jpy is None else self._to_sheet_number(float(item.unit_price_jpy)),
            "カート価格": "" if item.selling_price is None else self._to_sheet_number(float(item.selling_price)),
        }

    @staticmethod
    def _find_matching_value(header_name: str, value_by_header: dict[str, Any]) -> Any:
        for key, value in value_by_header.items():
            if key and key in header_name:
                return value
        return ""

    def _determine_target_row(self, worksheet, headers: list[str]) -> int:
        start_row = self.HEADER_ROW + 1
        key_col = self._choose_key_column(headers)
        last_filled_row = self._find_last_filled_row_index(worksheet, start_row=start_row, key_col=key_col)
        target_row = last_filled_row + 1
        if target_row > worksheet.row_count:
            worksheet.add_rows(target_row - worksheet.row_count)
        return target_row

    @staticmethod
    def _write_row(worksheet, target_row: int, header_cells: list[str], row_values: list[Any]) -> None:
        start_a1 = rowcol_to_a1(target_row, 1)
        end_a1 = rowcol_to_a1(target_row, len(header_cells))
        worksheet.update(
            f"{start_a1}:{end_a1}",
            [row_values],
            value_input_option="USER_ENTERED",
        )

    def _build_formula_copy_requests(
        self, worksheet, target_row: int, header_cells: list[str], row_values: list[Any]
    ) -> list[dict[str, Any]]:
        start_row = self.HEADER_ROW + 1
        if target_row <= start_row:
            return []

        prev_row = target_row - 1
        prev_cells = self._get_previous_row_formulas(worksheet, prev_row, len(header_cells))
        formula_cols = self._find_formula_columns(prev_cells, row_values, header_cells)

        logger.info("数式コピー対象列: %s", formula_cols)
        return self._create_copy_paste_requests(worksheet, prev_row, target_row, formula_cols)

    def _get_previous_row_formulas(self, worksheet, prev_row: int, col_count: int) -> list[Any]:
        prev_start_a1 = rowcol_to_a1(prev_row, 1)
        prev_end_a1 = rowcol_to_a1(prev_row, col_count)
        prev_row_values = worksheet.get(f"{prev_start_a1}:{prev_end_a1}", value_render_option="FORMULA")
        return prev_row_values[0] if prev_row_values else []

    def _find_formula_columns(
        self, prev_cells: list[Any], row_values: list[Any], header_cells: list[str]
    ) -> list[int]:
        formula_cols: list[int] = []
        for idx, prev_cell in enumerate(prev_cells):
            if self._should_copy_formula(idx, prev_cell, row_values, header_cells):
                formula_cols.append(idx)
        return formula_cols

    def _should_copy_formula(
        self, idx: int, prev_cell: Any, row_values: list[Any], header_cells: list[str]
    ) -> bool:
        is_formula = isinstance(prev_cell, str) and prev_cell.strip().startswith("=")
        if not is_formula:
            return False

        header_name = header_cells[idx].strip() if idx < len(header_cells) else ""
        if header_name in self.NEVER_COPY_FORMULA_COLUMNS:
            return False

        is_empty_now = str(row_values[idx]).strip() == "" if idx < len(row_values) else True
        is_formula_only_column = header_name in self.FORMULA_ONLY_COLUMNS

        if is_formula_only_column:
            logger.debug(
                "数式コピー対象列検出: idx=%d, header=%s, prev_cell=%s",
                idx, header_name, prev_cell
            )

        return is_empty_now or is_formula_only_column

    def _create_copy_paste_requests(
        self, worksheet, prev_row: int, target_row: int, formula_cols: list[int]
    ) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        for start_col, end_col in self._contiguous_ranges(formula_cols):
            requests.append({
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
            })
        return requests

    def _clear_basic_filter(self, spreadsheet, worksheet) -> dict[str, Any] | None:
        try:
            sheet_meta = self._find_sheet_metadata(spreadsheet, worksheet.id)
            if not sheet_meta:
                return None
            basic_filter = sheet_meta.get("basicFilter")
            if not basic_filter or not isinstance(basic_filter, dict):
                return None
            self._execute_batch_update(spreadsheet, [
                {"clearBasicFilter": {"sheetId": worksheet.id}}
            ])
            return basic_filter
        except Exception:
            return None

    def _restore_basic_filter(
        self, spreadsheet, worksheet, saved_filter: dict[str, Any] | None, target_row: int
    ) -> None:
        if not saved_filter:
            return
        try:
            bf_range = (saved_filter.get("range") or {}).copy()
            end_row_idx = bf_range.get("endRowIndex")
            desired_end = max(int(end_row_idx or 0), int(target_row) + 1)
            bf_range["endRowIndex"] = desired_end
            restored_filter = saved_filter.copy()
            restored_filter["range"] = bf_range
            self._execute_batch_update(spreadsheet, [
                {"setBasicFilter": {"filter": restored_filter}}
            ])
        except Exception:
            pass

    def _build_filter_view_expand_requests(
        self, spreadsheet, worksheet, target_row: int
    ) -> list[dict[str, Any]]:
        try:
            sheet_meta = self._find_sheet_metadata(spreadsheet, worksheet.id)
            if not sheet_meta:
                return []
            return self._build_filter_view_requests(sheet_meta, target_row)
        except Exception:
            return []

    @staticmethod
    def _find_sheet_metadata(spreadsheet, sheet_id: int) -> dict[str, Any] | None:
        meta = spreadsheet.fetch_sheet_metadata()
        sheets = meta.get("sheets", [])
        for s in sheets:
            props = (s or {}).get("properties", {})
            if props.get("sheetId") == sheet_id:
                return s
        return None

    @staticmethod
    def _build_basic_filter_request(sheet_meta: dict[str, Any], target_row: int) -> dict[str, Any] | None:
        basic_filter = sheet_meta.get("basicFilter")
        if not basic_filter or not isinstance(basic_filter, dict):
            return None

        bf_range = (basic_filter.get("range") or {}).copy()
        end_row_idx = bf_range.get("endRowIndex")
        # endRowIndexは0-based exclusiveなので、target_row(1-based)を含めるにはtarget_row + 1が必要
        desired_end = max(int(end_row_idx or 0), int(target_row) + 1)

        if end_row_idx is not None and int(end_row_idx) >= desired_end:
            return None

        bf_range["endRowIndex"] = desired_end
        new_filter = basic_filter.copy()
        new_filter["range"] = bf_range
        return {"setBasicFilter": {"filter": new_filter}}

    @staticmethod
    def _build_filter_view_requests(sheet_meta: dict[str, Any], target_row: int) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        filter_views = sheet_meta.get("filterViews") or []

        for view in filter_views:
            if not isinstance(view, dict):
                continue

            view_range = (view.get("range") or {}).copy()
            end_row_idx = view_range.get("endRowIndex")
            # endRowIndexは0-based exclusiveなので、target_row(1-based)を含めるにはtarget_row + 1が必要
            desired_end = max(int(end_row_idx or 0), int(target_row) + 1)

            if end_row_idx is not None and int(end_row_idx) >= desired_end:
                continue

            view_range["endRowIndex"] = desired_end
            new_view = view.copy()
            new_view["range"] = view_range
            requests.append({
                "updateFilterView": {
                    "filter": new_view,
                    "fields": "range",
                }
            })
        return requests

    @staticmethod
    def _execute_batch_update(spreadsheet, requests: list[dict[str, Any]]) -> None:
        if requests:
            spreadsheet.batch_update({"requests": requests})

    @staticmethod
    def _to_sheet_number(value: float) -> int | float:
        v = float(value)
        return int(v) if v.is_integer() else v

    @staticmethod
    def _find_last_filled_row_index(worksheet, *, start_row: int, key_col: int) -> int:
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
        header_cells = [str(h).strip() for h in headers]
        for i, name in enumerate(header_cells, start=1):
            if "ASIN" in name:
                return i
        for i, name in enumerate(header_cells, start=1):
            if ("注文番号" in name) or ("発注番号" in name):
                return i
        return 1

    @staticmethod
    def _contiguous_ranges(cols_0based: list[int]) -> list[tuple[int, int]]:
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
