from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizeToken:
    text: str
    values: frozenset[float]


@dataclass(frozen=True)
class MaterialRequest:
    message_id: str
    sent_at: int
    body: str
    size_tokens: tuple[SizeToken, ...]
    categories: tuple[str, ...]
