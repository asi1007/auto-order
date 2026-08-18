from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.material_request import MaterialRequest, SizeToken
from domain.value_objects.material_row import MaterialRow


@dataclass(frozen=True)
class PlannedOrder:
    request: MaterialRequest
    size_token: SizeToken
    material: MaterialRow
    quantity: int

    @property
    def piece_count(self) -> int:
        return self.quantity * self.material.lot_size


@dataclass(frozen=True)
class PendingRequest:
    request: MaterialRequest
    size_token: SizeToken | None
    candidates: tuple[MaterialRow, ...]
    reason: str


@dataclass(frozen=True)
class IngestPlan:
    orders: tuple[PlannedOrder, ...]
    pendings: tuple[PendingRequest, ...]

    @property
    def resolved_message_ids(self) -> tuple[str, ...]:
        pending_ids = {pending.request.message_id for pending in self.pendings}
        ordered_ids = dict.fromkeys(order.request.message_id for order in self.orders)
        return tuple(mid for mid in ordered_ids if mid not in pending_ids)

    @property
    def all_message_ids(self) -> tuple[str, ...]:
        ids = [order.request.message_id for order in self.orders]
        ids += [pending.request.message_id for pending in self.pendings]
        return tuple(dict.fromkeys(ids))

    def message_ids_sent_before(self, cutoff_epoch: int) -> tuple[str, ...]:
        requests = [order.request for order in self.orders]
        requests += [pending.request for pending in self.pendings]
        return tuple(
            dict.fromkeys(r.message_id for r in requests if r.sent_at < cutoff_epoch)
        )

    @property
    def quantity_by_row(self) -> dict[int, int]:
        return {order.material.row_number: order.quantity for order in self.orders}
