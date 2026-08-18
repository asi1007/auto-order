from __future__ import annotations

from domain.services.material_matcher import MaterialMatcher
from domain.value_objects.ingest_plan import IngestPlan, PendingRequest, PlannedOrder
from domain.value_objects.material_request import MaterialRequest, SizeToken

_REASON_NO_SIZE = "サイズ表記なし"
_REASON_NO_CANDIDATE = "候補なし"
_REASON_AMBIGUOUS = "候補が複数"
_REASON_NO_HISTORY = "発注実績なし"
_REASON_INDIVISIBLE = "ロット数に割り切れない"


class MaterialRequestPlanner:
    def __init__(
        self,
        matcher: MaterialMatcher,
        quantity_by_material: dict[str, int],
        order_quantity_overrides: dict[str, int] | None = None,
    ) -> None:
        self._matcher = matcher
        self._quantity_by_material = dict(quantity_by_material)
        self._order_quantity_overrides = dict(order_quantity_overrides or {})

    def plan(self, requests: list[MaterialRequest]) -> IngestPlan:
        orders: list[PlannedOrder] = []
        pendings: list[PendingRequest] = []

        for request in requests:
            if not request.size_tokens:
                pendings.append(self._pending(request, None, (), _REASON_NO_SIZE))
                continue
            for size_token in request.size_tokens:
                self._resolve_size_token(request, size_token, orders, pendings)

        return IngestPlan(orders=tuple(orders), pendings=tuple(pendings))

    def _resolve_size_token(
        self,
        request: MaterialRequest,
        size_token: SizeToken,
        orders: list[PlannedOrder],
        pendings: list[PendingRequest],
    ) -> None:
        match = self._matcher.match(size_token, request.categories)
        if not match.rows:
            pendings.append(self._pending(request, size_token, (), _REASON_NO_CANDIDATE))
            return
        if not match.is_unique:
            pendings.append(self._pending(request, size_token, match.rows, _REASON_AMBIGUOUS))
            return

        material = match.rows[0]
        override = self._order_quantity_overrides.get(material.name)
        if override is not None:
            orders.append(self._order(request, size_token, material, override))
            return

        piece_count = self._quantity_by_material.get(material.name)
        if piece_count is None:
            pendings.append(self._pending(request, size_token, (material,), _REASON_NO_HISTORY))
            return

        # 「発注数」列はロット数。発注ログの個数は ロット数 × ロットサイズ で記録されている。
        lot_size = material.lot_size or 1
        if piece_count % lot_size != 0:
            pendings.append(self._pending(request, size_token, (material,), _REASON_INDIVISIBLE))
            return
        quantity = piece_count // lot_size

        orders.append(self._order(request, size_token, material, quantity))

    @staticmethod
    def _order(request, size_token, material, quantity: int) -> PlannedOrder:
        return PlannedOrder(
            request=request, size_token=size_token, material=material, quantity=quantity
        )

    @staticmethod
    def _pending(
        request: MaterialRequest,
        size_token: SizeToken | None,
        candidates: tuple,
        reason: str,
    ) -> PendingRequest:
        return PendingRequest(
            request=request, size_token=size_token, candidates=candidates, reason=reason
        )
