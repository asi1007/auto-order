from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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
                quantity_per_item=3,
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
                quantity_per_item=5,
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
        # 単価は「合計」に「1商品辺り発注数」（max=5）を掛け算
        expected_unit_price = (100 + 100) * 5
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

    def test_merges_same_asin_across_groups_into_one_row_with_newline_separated_orders(self):
        """同一ASIN（B0FCHM6QQR）が別グループ・別注文番号で発注された場合、
        仕入管理シートには 1 行 + 注文番号は改行(\\n)区切りで併記される。"""
        # グループ1: 主部材 (qty=600 × unit=10.6 = 6360 が最大総額)
        main_orders = [
            Order(
                asin="B0FCHM6QQR",
                product_name="主部材",
                sales_product_name="A4 アクリルフォトフレーム",
                purchase_url="https://detail.1688.com/offer/802957666380.html",
                order_quantity=600,
                sales_order_quantity=600,
                unit_price=10.6,
                image_text="img_main",
                remark_text="",
                delivery_category="特別",
                lot_size=1,
                quantity_per_item=1,
            ),
        ]
        # グループ2: 補助部材 (qty=600 × unit=0.98 = 588 で総額小さい)
        sub_orders = [
            Order(
                asin="B0FCHM6QQR",
                product_name="補助部材",
                sales_product_name="A4 アクリルフォトフレーム",
                purchase_url="https://detail.1688.com/offer/570972837245.html",
                order_quantity=600,
                sales_order_quantity=600,
                unit_price=0.98,
                image_text="img_sub",
                remark_text="",
                delivery_category="",
                lot_size=1,
                quantity_per_item=1,
            ),
        ]
        results = [
            OrderGroup(order_group=main_orders, order_number="Y0806-260524011"),
            OrderGroup(order_group=sub_orders, order_number="Y0806-260524012"),
        ]

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

        # 1 行に統合されること
        assert repository_instance.append.call_count == 1
        item = repository_instance.append.call_args_list[0][0][0]

        # 注文番号が改行区切りで併記される
        assert item.order_number == "Y0806-260524011\nY0806-260524012"

        # 数量は主部材（最大総額）から
        assert item.quantity == 600

        # 原価は主部材+補助部材を合算した「1個あたり実原価」
        assert item.unit_price == pytest.approx(11.58)

        # URL は両方が改行で併記される
        assert "802957666380" in item.url
        assert "570972837245" in item.url
        assert "\n" in item.url

    def test_merged_unit_price_is_scaled_when_sub_part_quantity_differs(self):
        """補助部材の発注数が主部材と異なる場合、単純な単価の足し算ではなく
        総額を主部材の数量で割った「1個あたり実原価」になる。"""
        main_orders = [
            Order(
                asin="B0FCHM6QQR",
                product_name="主部材",
                sales_product_name="A4 アクリルフォトフレーム",
                purchase_url="https://detail.1688.com/offer/802957666380.html",
                order_quantity=600,
                sales_order_quantity=600,
                unit_price=10.6,
                image_text="",
                remark_text="",
                delivery_category="特別",
                lot_size=1,
                quantity_per_item=1,
            ),
        ]
        # 補助部材は主部材の 2 倍の本数（1商品あたり2本使う）
        sub_orders = [
            Order(
                asin="B0FCHM6QQR",
                product_name="補助部材",
                sales_product_name="A4 アクリルフォトフレーム",
                purchase_url="https://detail.1688.com/offer/570972837245.html",
                order_quantity=1200,
                sales_order_quantity=1200,
                unit_price=0.98,
                image_text="",
                remark_text="",
                delivery_category="",
                lot_size=1,
                quantity_per_item=1,
            ),
        ]
        results = [
            OrderGroup(order_group=main_orders, order_number="Y0806-260524011"),
            OrderGroup(order_group=sub_orders, order_number="Y0806-260524012"),
        ]

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

        assert item.quantity == 600
        # (600*10.6 + 1200*0.98) / 600 = 12.56
        assert item.unit_price == pytest.approx(12.56)


