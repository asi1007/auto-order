"""
order_automation.pyのテストコード
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from infrastructure.order_automation import OrderAutomation
from domain.entities.order import Order


class TestOrderAutomation:
    """OrderAutomationクラスのテスト"""
    
    @pytest.fixture
    def order_info(self):
        """テスト用の注文情報"""
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
        """OrderAutomationインスタンス"""
        return OrderAutomation(
            headless=True,
            email='test@example.com',
            password='testpass'
        )
    
    def test_initialization(self):
        """初期化のテスト"""
        automation = OrderAutomation(
            headless=True,
            email='test@example.com',
            password='testpass123'
        )
        
        assert automation.headless is True
        assert automation.email == 'test@example.com'
        assert automation.password == 'testpass123'
        assert automation.is_logged_in is False
        assert automation.playwright is None
        assert automation.browser is None
        assert automation.context is None
        assert automation.pages == []
    
    def test_initialization_without_credentials(self):
        """認証情報なしでの初期化テスト"""
        with pytest.raises(Exception) as exc_info:
            OrderAutomation(headless=False)
        assert "ログイン情報が設定されていません" in str(exc_info.value)
    
    @patch('infrastructure.order_automation.sync_playwright')
    def test_start_browser(self, mock_playwright, automation):
        """ブラウザ起動のテスト"""
        # モックの設定
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        
        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        
        # テスト実行
        automation.start_browser()
        
        # 検証
        assert automation.playwright is not None
        assert automation.browser is not None
        assert automation.context is not None
        mock_playwright_instance.chromium.launch.assert_called_once_with(
            headless=True,
            slow_mo=500
        )
    
    def test_close_browser(self, automation):
        """ブラウザクローズのテスト"""
        # モックの設定
        automation.context = Mock()
        automation.browser = Mock()
        automation.playwright = Mock()
        
        # テスト実行
        automation.close_browser()
        
        # 検証
        automation.context.close.assert_called_once()
        automation.browser.close.assert_called_once()
        automation.playwright.stop.assert_called_once()
    
    @patch('infrastructure.order_automation.sync_playwright')
    def test_login_success(self, mock_playwright, automation):
        """ログイン成功のテスト"""
        # モックの設定
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # ログイン後のURLを設定
        mock_page.url = 'https://yiwupassport.jp/dashboard'
        
        automation.start_browser()
        
        # テスト実行
        result = automation.login()
        
        # 検証
        assert result is True
        assert automation.is_logged_in is True
        mock_page.goto.assert_called_with('https://yiwupassport.jp/login', timeout=30000)
        mock_page.fill.assert_any_call('input[type="text"]', 'test@example.com')
        mock_page.fill.assert_any_call('input[type="password"]', 'testpass')
    
    @patch('infrastructure.order_automation.sync_playwright')
    def test_login_failure(self, mock_playwright, automation):
        """ログイン失敗のテスト"""
        # モックの設定
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # ログイン失敗（ログインページのまま）
        mock_page.url = 'https://yiwupassport.jp/login'
        
        automation.start_browser()
        
        # テスト実行
        result = automation.login()
        
        # 検証
        assert result is False
        assert automation.is_logged_in is False
    
    def test_login_without_credentials(self, mocker):
        """認証情報なしでのログインテスト"""
        with pytest.raises(Exception) as exc_info:
            OrderAutomation(headless=True)
        assert "ログイン情報が設定されていません" in str(exc_info.value)
    
    def test_fill_field_success(self, automation):
        """フィールド入力成功のテスト"""
        mock_page = Mock()
        mock_element = Mock()
        
        mock_page.query_selector.return_value = mock_element
        
        # テスト実行
        result = automation._fill_field(mock_page, 'test value', ['input[name="test"]'])
        
        # 検証
        assert result is True
        mock_page.wait_for_selector.assert_called_once_with(
            'input[name="test"]', 
            state='visible', 
            timeout=5000
        )
        mock_page.fill.assert_called_once_with('input[name="test"]', 'test value')
    
    def test_fill_field_not_found(self, automation):
        """フィールドが見つからない場合のテスト"""
        mock_page = Mock()
        mock_page.query_selector.return_value = None
        
        # テスト実行
        result = automation._fill_field(mock_page, 'test value', ['input[name="nonexistent"]'])
        
        # 検証
        assert result is False
    
    def test_fill_field_multiple_selectors(self, automation):
        """複数セレクタのテスト"""
        mock_page = Mock()
        
        # 最初のセレクタは見つからず、2番目で見つかる
        def query_selector_side_effect(selector):
            if selector == 'input[name="first"]':
                return None
            elif selector == 'input[name="second"]':
                return Mock()
            return None
        
        mock_page.query_selector.side_effect = query_selector_side_effect
        
        # テスト実行
        result = automation._fill_field(
            mock_page, 
            'test value', 
            ['input[name="first"]', 'input[name="second"]']
        )
        
        # 検証
        assert result is True
        assert mock_page.query_selector.call_count == 2
    
    @patch('infrastructure.order_automation.sync_playwright')
    def test_process_orders_empty_list(self, mock_playwright, automation):
        """空の注文グループのテスト"""
        # テスト実行
        automation.process_orders([])
        
        # ブラウザが起動されないことを検証
        assert automation.playwright is None
    
    def test_fill_order_form_multiple_products(self, automation):
        """複数商品を1つのフォームに入力するテスト"""
        mock_page = Mock()
        mock_element = Mock()
        
        mock_page.query_selector.return_value = mock_element
        automation.context = Mock()
        automation.context.new_page.return_value = mock_page
        
        # 3商品のグループ
        order_group = [
            Order(asin="B001", product_name="商品1", purchase_url="http://test.com", color_size_spec="Red", order_quantity=10, unit_price=100),
            Order(asin="B002", product_name="商品2", purchase_url="http://test.com", color_size_spec="Blue", order_quantity=20, unit_price=200),
            Order(asin="B003", product_name="商品3", purchase_url="http://test.com", color_size_spec="Green", order_quantity=30, unit_price=300),
        ]
        
        # テスト実行
        automation.fill_order_form(order_group)
        
        # 3商品分のフィールドが入力されることを検証
        # item_name1, item_name2, item_name3
        assert mock_page.fill.call_count >= 15  # 各商品5フィールド × 3商品
    
    @patch('infrastructure.order_automation.sync_playwright')
    def test_process_orders_without_login(self, mock_playwright):
        """ログイン情報なしでの注文処理テスト"""
        with pytest.raises(Exception):
            OrderAutomation(headless=True)
        
        order_groups = [[Order(asin="B001", product_name="テスト", purchase_url="http://test.com", color_size_spec="", order_quantity=1, unit_price=100)]]
        
        # モックの設定
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        
        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        
        # ログイン情報がないため例外が発生する
        with pytest.raises(Exception):
            automation.process_orders(order_groups)


class TestOrderAutomationIntegration:
    """統合テスト"""
    
    def test_order_data_structure(self):
        """注文データ構造のテスト"""
        order_info = Order(
            asin="B001TEST",
            product_name="テスト商品",
            purchase_url="http://example.com",
            color_size_spec="Red",
            order_quantity=5,
            unit_price=1000,
        )
        
        # 必須フィールドの確認
        assert order_info.asin
        assert order_info.product_name
        assert order_info.purchase_url
        assert isinstance(order_info.order_quantity, int)

