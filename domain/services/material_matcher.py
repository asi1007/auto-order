from __future__ import annotations

from dataclasses import dataclass

from domain.services.material_request_rules import CATEGORY_MATERIAL_PREDICATES
from domain.value_objects.material_request import SizeToken
from domain.value_objects.material_row import MaterialRow


@dataclass(frozen=True)
class MaterialMatch:
    size_token: SizeToken
    rows: tuple[MaterialRow, ...]

    @property
    def is_unique(self) -> bool:
        return len(self.rows) == 1


class MaterialMatcher:
    def __init__(self, rows: list[MaterialRow]) -> None:
        self._rows = tuple(rows)

    def match(self, size_token: SizeToken, categories: tuple[str, ...]) -> MaterialMatch:
        candidates = self._candidates_by_dimension(size_token)
        return MaterialMatch(
            size_token=size_token,
            rows=self._narrow_by_category(candidates, categories),
        )

    def _candidates_by_dimension(self, size_token: SizeToken) -> tuple[MaterialRow, ...]:
        return tuple(row for row in self._rows if size_token.values <= row.dimension_values)

    @staticmethod
    def _narrow_by_category(
        candidates: tuple[MaterialRow, ...], categories: tuple[str, ...]
    ) -> tuple[MaterialRow, ...]:
        predicates = [
            CATEGORY_MATERIAL_PREDICATES[category]
            for category in categories
            if category in CATEGORY_MATERIAL_PREDICATES
        ]
        if not predicates:
            return candidates

        narrowed = tuple(
            row for row in candidates if any(predicate(row.name) for predicate in predicates)
        )
        return narrowed or candidates
