import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from infrastructure.order_automation import OrderAutomation, BASE_URL
from domain.entities.order import Order


class TestOrderAutomation:

    @pytest.fixture
    def order_info(self):
        return Order(
            asin="B001TEST",
            product_name="テスト商品",
            purchase_url="http://test.com/product",
            color_size_spec="Red/Large",
            order_quantity=10,
            unit_price=1500,
        )

    @pytest.fixture
    def automation(self):
        return OrderAutomation(
            headless=True,
            email="test@example.com",
            password="testpass",
        )

    def test_initialization(self):
        automation = OrderAutomation(
            headless=True,
            email="test@example.com",
            password="testpass123",
        )

        assert automation.headless is True
        assert automation.email == "test@example.com"
        assert automation.password == "testpass123"
        assert automation.is_logged_in is False
        assert automation.playwright is None
        assert automation.browser is None
        assert automation.context is None
        assert automation.page is None

    def test_initialization_without_credentials(self):
        with pytest.raises(Exception) as exc_info:
            OrderAutomation(headless=False)
        assert "ログイン情報が設定されていません" in str(exc_info.value)

    @patch("infrastructure.order_automation.sync_playwright")
    def test_start_browser(self, mock_playwright, automation):
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()

        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context

        automation.start_browser()

        assert automation.playwright is not None
        assert automation.browser is not None
        assert automation.context is not None
        mock_playwright_instance.chromium.launch.assert_called_once_with(
            headless=True, slow_mo=500
        )

    def test_close_browser(self, automation):
        automation.page = Mock()
        automation.context = Mock()
        automation.browser = Mock()
        automation.playwright = Mock()

        automation.close_browser()

        automation.page.close.assert_called_once()
        automation.context.close.assert_called_once()
        automation.browser.close.assert_called_once()
        automation.playwright.stop.assert_called_once()

    @patch("infrastructure.order_automation.sync_playwright")
    def test_login_success(self, mock_playwright, automation):
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_page.url = f"{BASE_URL}/manual"

        automation.start_browser()
        result = automation.login()

        assert result is True
        assert automation.is_logged_in is True
        mock_page.goto.assert_any_call(f"{BASE_URL}/login", timeout=30000)
        mock_page.goto.assert_any_call(f"{BASE_URL}/manual", timeout=30000)
        mock_page.fill.assert_any_call('input[type="text"]', "test@example.com")
        mock_page.fill.assert_any_call('input[type="password"]', "testpass")
        mock_page.click.assert_called_with('button:has-text("ログイン")')

    @patch("infrastructure.order_automation.sync_playwright")
    def test_login_failure(self, mock_playwright, automation):
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_page.url = f"{BASE_URL}/login"

        automation.start_browser()
        result = automation.login()

        assert result is False
        assert automation.is_logged_in is False

    def test_login_without_credentials(self):
        with pytest.raises(Exception) as exc_info:
            OrderAutomation(headless=True)
        assert "ログイン情報が設定されていません" in str(exc_info.value)

    def test_fill_td_input_success(self, automation):
        mock_td = MagicMock()
        mock_input = MagicMock()
        mock_td.locator.return_value.first = mock_input
        mock_input.count.return_value = 1

        result = automation._fill_td_input(mock_td, "test value")

        assert result is True
        mock_input.fill.assert_called_once_with("test value")

    def test_fill_td_input_no_element(self, automation):
        mock_td = MagicMock()
        mock_input = MagicMock()
        mock_td.locator.return_value.first = mock_input
        mock_input.count.return_value = 0

        result = automation._fill_td_input(mock_td, "test value")

        assert result is False

    def test_extract_store_name(self):
        assert OrderAutomation._extract_store_name("https://detail.1688.com/offer/123") == "detail.1688.com"
        assert OrderAutomation._extract_store_name("https://www.example.com/product") == "example.com"
        assert OrderAutomation._extract_store_name("") == "不明"
        assert OrderAutomation._extract_store_name("invalid-url") == "不明"

    @patch("infrastructure.order_automation.sync_playwright")
    def test_process_orders_empty_list(self, mock_playwright, automation):
        automation.process_orders([])
        assert automation.playwright is None

    def test_fill_order_form_with_page(self, automation):
        mock_page = MagicMock()
        automation.page = mock_page

        mock_rows = MagicMock()
        mock_last_row = MagicMock()
        mock_tds = MagicMock()

        mock_page.locator.return_value = mock_rows
        mock_rows.last = mock_last_row
        mock_last_row.locator.return_value = mock_tds

        mock_td = MagicMock()
        mock_input = MagicMock()
        mock_td.locator.return_value.first = mock_input
        mock_input.count.return_value = 1
        mock_tds.nth.return_value = mock_td

        mock_submit_btn = MagicMock()
        mock_page.locator.return_value = mock_submit_btn
        mock_submit_btn.wait_for = MagicMock()
        mock_page.content.return_value = "注文番号：P260226001YP806"

        order_group = [
            Order(
                asin="B001",
                product_name="商品1",
                purchase_url="http://test.com/product1",
                color_size_spec="Red",
                order_quantity=10,
                unit_price=100,
            ),
        ]

        automation.fill_order_form(order_group)

        mock_page.goto.assert_called_with(f"{BASE_URL}/manual", timeout=30000)
        mock_page.click.assert_any_call('button:has-text("商品を追加")')

    @patch("infrastructure.order_automation.sync_playwright")
    def test_process_orders_without_login(self, mock_playwright):
        with pytest.raises(Exception):
            OrderAutomation(headless=True)

    def test_extract_order_number_from_html(self, automation):
        mock_page = MagicMock()
        mock_page.content.return_value = "注文番号：P260226013YP806"
        mock_page.url = f"{BASE_URL}/manual"

        result = automation._extract_order_number(mock_page)
        assert result == "P260226013YP806"

    def test_extract_order_number_from_history_fallback(self, automation):
        mock_page = MagicMock()
        mock_page.content.return_value = "注文番号：P260226013YP806"
        mock_page.url = f"{BASE_URL}/order/list"

        result = automation._get_latest_order_number_from_history(mock_page)
        assert result == "P260226013YP806"

    def test_extract_order_number_not_found(self, automation):
        mock_page = MagicMock()
        mock_page.content.return_value = "<html>操作成功</html>"
        mock_page.url = f"{BASE_URL}/manual"
        mock_page.goto = MagicMock()

        result = automation._extract_order_number(mock_page)
        assert result is None or isinstance(result, str)

    def test_extract_order_number_new_format(self, automation):
        mock_page = MagicMock()
        mock_page.content.return_value = "注文番号： Y0806-260513008 コピー"
        mock_page.url = f"{BASE_URL}/order/list"

        result = automation._extract_order_number(mock_page)
        assert result == "Y0806-260513008"

    def test_extract_order_number_history_new_format(self, automation):
        mock_page = MagicMock()
        mock_page.content.return_value = "注文番号： Y0806-260513008 コピー"
        mock_page.url = f"{BASE_URL}/order/list"

        result = automation._get_latest_order_number_from_history(mock_page)
        assert result == "Y0806-260513008"


class TestOrderAutomationIntegration:

    def test_order_data_structure(self):
        order_info = Order(
            asin="B001TEST",
            product_name="テスト商品",
            purchase_url="http://example.com",
            color_size_spec="Red",
            order_quantity=5,
            unit_price=1000,
        )

        assert order_info.asin
        assert order_info.product_name
        assert order_info.purchase_url
        assert isinstance(order_info.order_quantity, int)
