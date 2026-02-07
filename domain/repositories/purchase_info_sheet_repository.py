from __future__ import annotations

from typing import Protocol

from domain.value_objects.purchase_info_sheet import PurchaseInfoSheet


class PurchaseInfoSheetRepository(Protocol):
    def read(self, sheet_url: str, sheet_name: str = "仕入情報") -> PurchaseInfoSheet: ...
    def read_selling_prices(self, sheet_url: str, sheet_name: str = "納品状況") -> dict[str, float]: ...

