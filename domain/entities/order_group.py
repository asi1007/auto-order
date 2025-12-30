from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.entities.order import Order


@dataclass(frozen=True)
class OrderGroup:
    order_group: list[Order]
    order_number: Optional[str]
    error: Optional[str] = None

