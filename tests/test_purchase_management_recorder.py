from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.entities.order import Order
from domain.entities.order_group import OrderGroup
from infrastructure.purchase_management_recorder import record_purchase_management


class TestRecordPurchaseManagement:
    def test_records_each_order_to_management_sheet(self):
        orders = [
            Order(asin="A1", product_name="p1", sales_product_name="売上p1", purchase_url="u1", order_quantity=2, sales_order_quantity=2, unit_price=100, image_text="img1", remark_text="memo1", delivery_category="特別"),
            Order(asin="A2", product_name="p2", sales_product_name="売上p2", purchase_url="u2", order_quantity=1, sales_order_quantity=1, unit_price=None, image_text="", remark_text="", delivery_category=""),
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

        # 仕入管理に書く数量は sales_order_quantity を優先する
        first_item = repository_instance.append.call_args_list[0][0][0]
        assert first_item.quantity == 2

    def test_groups_orders_by_asin_and_records_one_row_per_asin(self):
        orders = [
            Order(
                asin="A1",
                product_name="p1",
                sales_product_name="売上p1",
                purchase_url="u1",
                order_quantity=2,
                sales_order_quantity=2,
                unit_price=100,
                image_text="img1",
                remark_text="memo1",
                delivery_category="特別",
                lot_size=1,
            ),
            Order(
                asin="A1",
                product_name="p1",
                sales_product_name="売上p1",
                purchase_url="u1",
                order_quantity=3,
                sales_order_quantity=3,
                unit_price=100,
                image_text="img1",
                remark_text="memo1",
                delivery_category="特別",
                lot_size=2,
            ),
        ]
        results = [OrderGroup(order_group=orders, order_number="2025-99999999")]

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

        # 同一ASINは1行に集約
        assert repository_instance.append.call_count == 1
        item = repository_instance.append.call_args_list[0][0][0]
        # quantity = sales_order_quantity優先。さらに lot_size を掛けた値の「平均」
        expected_quantity = ((2 * 1) + (3 * 2)) / 2
        assert item.quantity == expected_quantity
        # 単価は「合計」に「一商品辺りの発注数」を掛け算
        expected_unit_price = (100 + 100) * expected_quantity
        assert item.unit_price == expected_unit_price

    def test_selling_price_is_passed_to_purchase_management_item(self):
        """Orderのselling_priceがPurchaseManagementItemに伝搬される"""
        orders = [
            Order(
                asin="A1",
                product_name="p1",
                sales_product_name="売上p1",
                purchase_url="u1",
                order_quantity=2,
                sales_order_quantity=2,
                unit_price=100,
                image_text="img1",
                remark_text="memo1",
                delivery_category="特別",
                selling_price=1980.0,
            ),
        ]
        results = [OrderGroup(order_group=orders, order_number="2025-99999999")]

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

        item = repository_instance.append.call_args_list[0][0][0]
        assert item.selling_price == 1980.0

    def test_selling_price_none_when_order_has_no_selling_price(self):
        """Orderにselling_priceがない場合はNoneになる"""
        orders = [
            Order(
                asin="A1",
                product_name="p1",
                sales_product_name="売上p1",
                purchase_url="u1",
                order_quantity=2,
                sales_order_quantity=2,
                unit_price=100,
                image_text="",
                remark_text="",
                delivery_category="",
            ),
        ]
        results = [OrderGroup(order_group=orders, order_number="2025-99999999")]

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

        item = repository_instance.append.call_args_list[0][0][0]
        assert item.selling_price is None


