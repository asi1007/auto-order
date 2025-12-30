from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.entities.order_group import OrderGroup
from domain.entities.order import Order
from infrastructure.purchase_history_recorder import record_purchase_history


class TestRecordPurchaseHistoryWithResults:
    def test_record_purchase_history_sets_order_number_and_appends(self):
        order = Order(asin="A1", product_name="テスト商品", purchase_url="https://example.com", order_quantity=2)
        results = [OrderGroup(order_group=[order], order_number="2025-12345678")]

        base_mock = MagicMock()
        base_mock.client = MagicMock()

        repository_instance = MagicMock()

        with patch(
            "infrastructure.purchase_history_recorder.BaseSheetsRepository",
            return_value=base_mock,
        ), patch(
            "infrastructure.purchase_history_recorder.SheetsPurchaseHistoryRepository",
            return_value=repository_instance,
        ):
            record_purchase_history(
                credentials_file="creds.json",
                history_sheet_url="https://example.com/sheet",
                order_groups=results,
                sheet_name="履歴",
            )

        assert repository_instance.append.call_count == 1
        appended_item = repository_instance.append.call_args[0][0]
        assert appended_item.order_number == "2025-12345678"


