from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.entities.order import Order
from domain.entities.order_group import OrderGroup
from infrastructure.purchase_management_recorder import record_purchase_management


class TestRecordPurchaseManagement:
    def test_records_each_order_to_management_sheet(self):
        orders = [
            Order(asin="A1", product_name="p1", sales_product_name="売上p1", purchase_url="u1", order_quantity=2, unit_price=100, image_text="img1"),
            Order(asin="A2", product_name="p2", sales_product_name="売上p2", purchase_url="u2", order_quantity=1, unit_price=None, image_text=""),
        ]
        results = [OrderGroup(order_group=orders, order_number="2025-12345678")]

        base_mock = MagicMock()
        base_mock.client = MagicMock()

        repository_instance = MagicMock()

        with patch(
            "infrastructure.purchase_management_recorder.BaseSheetsRepository",
            return_value=base_mock,
        ), patch(
            "infrastructure.purchase_management_recorder.SheetsPurchaseManagementRepository",
            return_value=repository_instance,
        ):
            record_purchase_management(
                credentials_file="creds.json",
                management_sheet_url="https://example.com/sheet?gid=1#gid=1",
                order_groups=results,
                management_sheet_name="仕入管理",
            )

        assert repository_instance.append.call_count == 2


