from __future__ import annotations

from typing import Protocol

from domain.value_objects.purchase_management import PurchaseManagementItem


class PurchaseManagementSheetRepository(Protocol):
    def append(self, item: PurchaseManagementItem) -> None: ...


