"""
購入履歴のValueObject
"""

from typing import List, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from domain.repositories.purchase_history_repository import PurchaseHistoryRepository


@dataclass(frozen=True)
class PurchaseHistoryItem:
    purchase_date: str
    product_name: str
    url: str
    detail: str
    quantity: int
    price: float
    order_number: str = ""
    material_name: str = ""
    
    def __post_init__(self):
        if not self.product_name or not self.product_name.strip():
            raise ValueError("商品名は必須です")
        if not self.url or not self.url.strip():
            raise ValueError("URLは必須です")
        if self.quantity < 0:
            raise ValueError("数量は0以上である必要があります")
        if self.price < 0:
            raise ValueError("価格は0以上である必要があります")


class PurchaseHistorySheet:
    def __init__(self, items: List[PurchaseHistoryItem]):
        self._items = tuple(items)
    
    @property
    def items(self) -> List[PurchaseHistoryItem]:
        return list(self._items)
    
    def add_history(
        self,
        item: PurchaseHistoryItem,
        repository: "PurchaseHistoryRepository | None" = None,
    ) -> "PurchaseHistorySheet":
        new_items = list(self._items) + [item]
        if repository is not None:
            repository.append(item)
        return PurchaseHistorySheet(items=new_items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __repr__(self) -> str:
        return f"PurchaseHistorySheet(items={len(self._items)})"


