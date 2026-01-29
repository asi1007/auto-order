from __future__ import annotations

from typing import Protocol

from domain.value_objects.sales_sheet import SalesSheet


class SalesSheetRepository(Protocol):
    def read(self, sheet_url: str, sheet_name: str = "売上/日") -> SalesSheet: ...

    def clear_order_quantities(self, sheet_url: str, asins: list[str], sheet_name: str = "売上/日") -> int: ...

