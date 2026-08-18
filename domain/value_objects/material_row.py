from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import cached_property

_PARENTHESIZED_PATTERN = re.compile(r"[（(\[][^）)\]]*[）)\]]")
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class MaterialRow:
    row_number: int
    name: str
    detail: str
    lot_size: int = 1

    @cached_property
    def dimension_values(self) -> frozenset[float]:
        normalized = unicodedata.normalize("NFKC", self.detail)
        without_counts = _PARENTHESIZED_PATTERN.sub(" ", normalized)
        return frozenset(float(v) for v in _NUMBER_PATTERN.findall(without_counts))
