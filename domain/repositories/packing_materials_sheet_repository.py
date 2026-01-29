from __future__ import annotations

from typing import Protocol

from domain.value_objects.packing_materials_sheet import PackingMaterialsSheet


class PackingMaterialsSheetRepository(Protocol):
    def read(self, sheet_url: str, sheet_name: str = "使用資材") -> PackingMaterialsSheet: ...

    def clear_order_quantities(self, sheet_url: str, material_names: list[str], sheet_name: str = "使用資材") -> int: ...

