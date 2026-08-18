from __future__ import annotations

import logging

from domain.services.material_matcher import MaterialMatcher
from domain.services.material_request_parser import MaterialRequestParser
from domain.services.material_request_planner import MaterialRequestPlanner
from domain.value_objects.ingest_plan import IngestPlan
from domain.value_objects.material_request import MaterialRequest

logger = logging.getLogger(__name__)


class IngestMaterialRequests:
    def __init__(
        self,
        chatwork_client,
        packing_repository,
        history_repository,
        store,
        room_id: str,
        packing_sheet_url: str,
        packing_sheet_name: str = "使用資材",
        order_quantity_overrides: dict[str, int] | None = None,
    ) -> None:
        self._chatwork_client = chatwork_client
        self._packing_repository = packing_repository
        self._history_repository = history_repository
        self._store = store
        self._room_id = room_id
        self._packing_sheet_url = packing_sheet_url
        self._packing_sheet_name = packing_sheet_name
        self._order_quantity_overrides = dict(order_quantity_overrides or {})
        self._parser = MaterialRequestParser()

    def build_plan(self) -> IngestPlan:
        requests = self._collect_unprocessed_requests()
        if not requests:
            return IngestPlan(orders=(), pendings=())

        material_rows = self._packing_repository.read_material_rows(
            self._packing_sheet_url, sheet_name=self._packing_sheet_name
        )
        planner = MaterialRequestPlanner(
            matcher=MaterialMatcher(material_rows),
            quantity_by_material=self._history_repository.latest_quantity_by_material(),
            order_quantity_overrides=self._order_quantity_overrides,
        )
        return planner.plan(requests)

    def apply(self, plan: IngestPlan) -> int:
        quantity_by_row = plan.quantity_by_row
        if not quantity_by_row:
            return 0

        written = self._packing_repository.set_order_quantities(
            self._packing_sheet_url, quantity_by_row, sheet_name=self._packing_sheet_name
        )
        resolved_message_ids = list(plan.resolved_message_ids)
        if resolved_message_ids:
            self._store.mark_processed(resolved_message_ids)
        return written

    def mark_all_as_processed(self, plan: IngestPlan) -> int:
        message_ids = list(plan.all_message_ids)
        if not message_ids:
            return 0
        self._store.mark_processed(message_ids)
        return len(message_ids)

    def mark_as_processed_before(self, plan: IngestPlan, cutoff_epoch: int) -> int:
        message_ids = list(plan.message_ids_sent_before(cutoff_epoch))
        if not message_ids:
            return 0
        self._store.mark_processed(message_ids)
        return len(message_ids)

    def _collect_unprocessed_requests(self) -> list[MaterialRequest]:
        requests: list[MaterialRequest] = []
        for message in self._chatwork_client.fetch_messages(self._room_id):
            message_id = str(message["message_id"])
            if self._store.is_processed(message_id):
                continue
            request = self._parser.parse(
                message_id=message_id,
                sent_at=int(message["send_time"]),
                body=str(message["body"]),
            )
            if request is not None:
                requests.append(request)
        return requests
