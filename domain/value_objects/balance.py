from __future__ import annotations

import re
from dataclasses import dataclass

_AMOUNT_PATTERN = re.compile(r"([\d,]+(?:\.\d+)?)")


def _parse_amount(text: str) -> float:
    if not text:
        return 0.0
    match = _AMOUNT_PATTERN.search(text)
    if not match:
        return 0.0
    return float(match.group(1).replace(",", ""))


@dataclass(frozen=True)
class Balance:
    cny: float
    jpy: float

    @classmethod
    def from_texts(cls, cny_text: str, jpy_text: str) -> "Balance":
        return cls(cny=_parse_amount(cny_text), jpy=_parse_amount(jpy_text))

    def covers(self, required_cny: float) -> bool:
        return self.cny >= required_cny

    def shortfall(self, required_cny: float) -> float:
        return max(0.0, required_cny - self.cny)
