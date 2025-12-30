from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class OrderGroupResult:
    order_group: list[dict[str, Any]]
    order_number: Optional[str]
    error: Optional[str] = None

