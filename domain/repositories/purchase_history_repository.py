from __future__ import annotations

from typing import Protocol

from domain.value_objects.purchase_history import PurchaseHistoryItem


class PurchaseHistoryRepository(Protocol):
    def append(self, item: PurchaseHistoryItem) -> None: ...

