from __future__ import annotations

from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository
from domain.value_objects.material_row import MaterialRow
from domain.value_objects.packing_materials_sheet import PackingMaterialsSheet
from gspread.utils import rowcol_to_a1


class SheetsPackingMaterialsSheetRepository(BaseSheetsRepository):
    def read(self, sheet_url: str, sheet_name: str = "使用資材") -> PackingMaterialsSheet:
        worksheet = self.open_worksheet(sheet_url, sheet_name)
        return PackingMaterialsSheet.from_values(worksheet.get_all_values())

    def read_material_rows(self, sheet_url: str, sheet_name: str = "使用資材") -> list[MaterialRow]:
        worksheet = self.open_worksheet(sheet_url, sheet_name)
        data = worksheet.get_all_values()
        header_idx = self._find_header_row_index(data)
        idx_name = self._find_column_index(data[header_idx], "資材名称")
        idx_detail = self._find_column_index(data[header_idx], "詳細")
        idx_lot = self._find_column_index(data[header_idx], "ロットサイズ")

        rows: list[MaterialRow] = []
        for row_num_1based, row in enumerate(data[header_idx + 1 :], start=header_idx + 2):
            name = str(row[idx_name]).strip() if idx_name < len(row) else ""
            if not name:
                continue
            detail = str(row[idx_detail]).strip() if idx_detail < len(row) else ""
            rows.append(
                MaterialRow(
                    row_number=row_num_1based,
                    name=name,
                    detail=detail,
                    lot_size=self._to_lot_size(row[idx_lot] if idx_lot < len(row) else ""),
                )
            )
        return rows

    def set_order_quantities(
        self, sheet_url: str, quantity_by_row: dict[int, int], sheet_name: str = "使用資材"
    ) -> int:
        if not quantity_by_row:
            return 0

        worksheet = self.open_worksheet(sheet_url, sheet_name)
        data = worksheet.get_all_values()
        header_idx = self._find_header_row_index(data)
        _, idx_qty = self._find_name_and_qty_column_indices(data[header_idx])

        for row_num in sorted(quantity_by_row):
            cell = rowcol_to_a1(row_num, idx_qty + 1)
            worksheet.update(cell, [[quantity_by_row[row_num]]], value_input_option="USER_ENTERED")
        return len(quantity_by_row)

    @staticmethod
    def _to_lot_size(value: str) -> int:
        text = str(value).strip().replace(",", "")
        if not text:
            return 1
        return max(int(float(text)), 1)

    @staticmethod
    def _find_column_index(header_row: list[str], column_name: str) -> int:
        for i, col in enumerate(header_row):
            if str(col).strip() == column_name:
                return i
        raise Exception(f"列が見つかりません: {column_name}")

    @staticmethod
    def _find_header_row_index(data: list[list[str]]) -> int:
        """
        ヘッダー行を検出（資材名称 + 発注数 がある行）。
        見つからない場合はPackingMaterialsSheetのデフォルト（2行目）に寄せる。
        """
        for idx, row in enumerate(data):
            row_str = [str(c).strip() for c in row]
            has_name = any(c == "資材名称" for c in row_str)
            has_qty = any(c == "発注数" for c in row_str)
            if has_name and has_qty:
                return idx
        return 1  # 2行目（0-based）

    @staticmethod
    def _find_name_and_qty_column_indices(header_row: list[str]) -> tuple[int, int]:
        idx_name: int | None = None
        idx_qty: int | None = None
        for i, col in enumerate(header_row):
            col_str = str(col).strip()
            if idx_name is None and col_str == "資材名称":
                idx_name = i
            if idx_qty is None and col_str == "発注数":
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

