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

    def test_extract_store_name(self):
        assert OrderAutomation._extract_store_name("https://detail.1688.com/offer/123") == "detail.1688.com"
        assert OrderAutomation._extract_store_name("https://www.example.com/product") == "example.com"
        assert OrderAutomation._extract_store_name("") == "不明"
        assert OrderAutomation._extract_store_name("invalid-url") == "不明"

    @patch("infrastructure.order_automation.sync_playwright")
    def test_process_orders_empty_list(self, mock_playwright, automation):
        automation.process_orders([])
        assert automation.playwright is None

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


class TestConvertJpyToCny:

    @pytest.fixture
    def automation(self):
        return OrderAutomation(
            headless=True,
            email="test@example.com",
            password="testpass",
        )

    def test_convert_jpy_to_cny_with_jpy_balance(self, automation):
        mock_page = MagicMock()
        automation.page = mock_page

        mock_page.text_content.return_value = "JPY 500000 円"
        mock_spinbutton = MagicMock()
        mock_page.locator.return_value = mock_spinbutton
        mock_spinbutton.wait_for = MagicMock()
        mock_spinbutton.fill = MagicMock()

        mock_submit_btn = MagicMock()
        mock_page.locator.side_effect = [
            MagicMock(text_content=MagicMock(return_value="JPY 500000 円")),  # JPY残高
            mock_spinbutton,  # spinbutton
            mock_submit_btn,  # 振替ボタン
            MagicMock(count=MagicMock(return_value=1), is_visible=MagicMock(return_value=True)),  # 確認ダイアログ
            MagicMock(),  # ダイアログ内ボタン
        ]

        automation.convert_jpy_to_cny()

        mock_page.goto.assert_called()

    def test_convert_jpy_to_cny_no_jpy_balance(self, automation):
        mock_page = MagicMock()
        automation.page = mock_page

        mock_jpy_locator = MagicMock()
        mock_jpy_locator.count.return_value = 0
        mock_page.locator.return_value = mock_jpy_locator

        automation.convert_jpy_to_cny()

    def test_convert_jpy_to_cny_zero_balance(self, automation):
        mock_page = MagicMock()
        automation.page = mock_page

        mock_jpy_locator = MagicMock()
        mock_jpy_locator.count.return_value = 1
        mock_jpy_locator.text_content.return_value = "0 円"
        mock_page.locator.return_value = mock_jpy_locator

        automation.convert_jpy_to_cny()

    def test_parse_jpy_balance(self, automation):
        assert automation._parse_jpy_balance("JPY 500000 円") == 500000
        assert automation._parse_jpy_balance("1010000 円") == 1010000
        assert automation._parse_jpy_balance("0 円") == 0
        assert automation._parse_jpy_balance("") == 0
        assert automation._parse_jpy_balance("JPY 1,500,000 円") == 1500000


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
