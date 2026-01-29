from __future__ import annotations

from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository
from domain.value_objects.packing_materials_sheet import PackingMaterialsSheet
from gspread.utils import rowcol_to_a1


class SheetsPackingMaterialsSheetRepository(BaseSheetsRepository):
    def read(self, sheet_url: str, sheet_name: str = "使用資材") -> PackingMaterialsSheet:
        worksheet = self.open_worksheet(sheet_url, sheet_name)
        return PackingMaterialsSheet.from_values(worksheet.get_all_values())

    @staticmethod
    def _find_header_row_index(data: list[list[str]]) -> int:
        """
        ヘッダー行を検出（資材名称 + 発注数 がある行）。
        見つからない場合はPackingMaterialsSheetのデフォルト（2行目）に寄せる。
        """
        for idx, row in enumerate(data):
            row_str = [str(c).strip() for c in row]
            has_name = any("資材名称" in c for c in row_str)
            has_qty = any("発注数" in c for c in row_str)
            if has_name and has_qty:
                return idx
        return 1  # 2行目（0-based）

    @staticmethod
    def _find_name_and_qty_column_indices(header_row: list[str]) -> tuple[int, int]:
        idx_name: int | None = None
        idx_qty: int | None = None
        for i, col in enumerate(header_row):
            col_str = str(col).strip()
            if idx_name is None and "資材名称" in col_str:
                idx_name = i
            if idx_qty is None and "発注数" in col_str:
                idx_qty = i
        if idx_name is None:
            idx_name = 0
        if idx_qty is None:
            if len(header_row) < 2:
                raise Exception("シートの列数が不足しています（資材名称/発注数の列が見つかりません）")
            idx_qty = 1
        return int(idx_name), int(idx_qty)

    @staticmethod
    def _contiguous_ranges(rows_1based: list[int]) -> list[tuple[int, int]]:
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

    def clear_order_quantities(self, sheet_url: str, material_names: list[str], sheet_name: str = "使用資材") -> int:
        """
        発注完了した資材（資材名称）の「発注数」セルを空欄に戻す。
        戻り値: 空欄にした行数
        """
        if not material_names:
            return 0

        worksheet = self.open_worksheet(sheet_url, sheet_name)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            raise Exception("シートにデータがありません（ヘッダー行が見つかりません）")

        header_idx = self._find_header_row_index(data)
        if header_idx >= len(data) - 1:
            return 0

        header_row = data[header_idx]
        idx_name, idx_qty = self._find_name_and_qty_column_indices(header_row)

        target_names = {str(n).strip() for n in material_names if str(n).strip()}
        if not target_names:
            return 0

        start_row_1based = header_idx + 2  # データ開始行（1-based）
        rows_to_clear: list[int] = []
        for row_num_1based, row in enumerate(data[header_idx + 1 :], start=start_row_1based):
            name_value = ""
            if idx_name < len(row):
                name_value = str(row[idx_name]).strip()
            if name_value in target_names:
                rows_to_clear.append(int(row_num_1based))

        if not rows_to_clear:
            return 0

        qty_col_1based = idx_qty + 1
        for start_row, end_row in self._contiguous_ranges(rows_to_clear):
            start_a1 = rowcol_to_a1(start_row, qty_col_1based)
            end_a1 = rowcol_to_a1(end_row, qty_col_1based)
            worksheet.update(
                f"{start_a1}:{end_a1}",
                [[""] for _ in range(end_row - start_row + 1)],
                value_input_option="USER_ENTERED",
            )

        return len(set(rows_to_clear))

