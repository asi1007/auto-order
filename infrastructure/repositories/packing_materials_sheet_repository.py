from __future__ import annotations

from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository
from domain.value_objects.packing_materials_sheet import PackingMaterialsSheet


class SheetsPackingMaterialsSheetRepository(BaseSheetsRepository):
    def read(self, sheet_url: str, sheet_name: str = "使用資材") -> PackingMaterialsSheet:
        worksheet = self.open_worksheet(sheet_url, sheet_name)
        return PackingMaterialsSheet.from_values(worksheet.get_all_values())

