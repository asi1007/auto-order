from __future__ import annotations

import re
import unicodedata

from domain.services.material_request_rules import (
    CATEGORY_MESSAGE_KEYWORDS,
    REQUEST_KEYWORDS,
    SHORTAGE_KEYWORDS,
)
from domain.value_objects.material_request import MaterialRequest, SizeToken

_QUOTE_PATTERN = re.compile(r"\[qt\].*?\[/qt\]", re.DOTALL)
_TAG_PATTERN = re.compile(r"\[[^\]]*\]")
_SIZE_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:mm|cm)?\s*(?:[*×x]\s*\d+(?:\.\d+)?\s*(?:mm|cm)?\s*)+",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")

_MINIMUM_DIMENSION_COUNT = 2


class MaterialRequestParser:
    def parse(self, message_id: str, sent_at: int, body: str) -> MaterialRequest | None:
        text = self._to_plain_text(body)
        if not self._is_material_shortage_request(text):
            return None

        return MaterialRequest(
            message_id=message_id,
            sent_at=sent_at,
            body=text,
            size_tokens=self._extract_size_tokens(text),
            categories=self._extract_categories(text),
        )

    @staticmethod
    def _to_plain_text(body: str) -> str:
        without_quotes = _QUOTE_PATTERN.sub(" ", body)
        without_tags = _TAG_PATTERN.sub(" ", without_quotes)
        return unicodedata.normalize("NFKC", without_tags)

    @staticmethod
    def _is_material_shortage_request(text: str) -> bool:
        has_shortage = any(keyword in text for keyword in SHORTAGE_KEYWORDS)
        has_request = any(keyword in text for keyword in REQUEST_KEYWORDS)
        return has_shortage and has_request

    @staticmethod
    def _extract_size_tokens(text: str) -> tuple[SizeToken, ...]:
        tokens: list[SizeToken] = []
        for match in _SIZE_PATTERN.finditer(text):
            token_text = match.group(0).strip()
            values = frozenset(float(v) for v in _NUMBER_PATTERN.findall(token_text))
            if len(values) >= _MINIMUM_DIMENSION_COUNT:
                tokens.append(SizeToken(text=token_text, values=values))
        return tuple(tokens)

    @staticmethod
    def _extract_categories(text: str) -> tuple[str, ...]:
        lowered = text.lower()
        return tuple(
            category
            for category, keywords in CATEGORY_MESSAGE_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        )
