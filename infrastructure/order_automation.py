"""
Playwrightを使用してイーウーパスポートの注文フォームに自動入力するモジュール
"""

from playwright.sync_api import sync_playwright, Page, Browser
from typing import List, Dict, Optional
import time
import logging
import re
import os

from domain.entities.order_group_result import OrderGroupResult


class OrderAutomation:
    """イーウーパスポートの注文自動化クラス"""
    
    def __init__(self, headless: bool = False, email: str = None, password: str = None):
        self.headless = headless
        self.email = email
        self.password = password
        self.playwright = None
        self.browser = None
        self.context = None
        self.pages = []
        self.is_logged_in = False
        self.logger = logging.getLogger(__name__)
        if not self.email or not self.password:
            self.logger.error("エラー: イーウーパスポートのログイン情報が設定されていません")
            self.logger.error(".envファイルにYIWUPASSPORT_EMAILとYIWUPASSPORT_PASSWORDを設定してください")
            raise Exception("ログイン情報が設定されていません")

    @classmethod
    def from_env(cls, headless: bool = False) -> "OrderAutomation":
        email = os.getenv("YIWUPASSPORT_EMAIL")
        password = os.getenv("YIWUPASSPORT_PASSWORD")
        return cls(headless=headless, email=email, password=password)
    
    def start_browser(self):
        """ブラウザを起動"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=500  # 動作を少しゆっくりにして確認しやすく
            )
            self.context = self.browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
            self.logger.info("✓ ブラウザを起動しました")
        except Exception as e:
            raise Exception(f"ブラウザの起動に失敗しました: {e}")
    
    def close_browser(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.logger.info("✓ ブラウザを閉じました")
        except Exception as e:
            self.logger.error(f"ブラウザのクローズ中にエラーが発生しました: {e}")
    
    def login(self):
        if not self.email or not self.password:
            raise Exception("ログイン情報が設定されていません")
        
        try:
            self.logger.info("イーウーパスポートにログインしています...")
            
            page = self.context.new_page()
            page.goto('https://yiwupassport.jp/login', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            
            email_selector = 'input[type="text"]'
            page.fill(email_selector, self.email)
            
            password_selector = 'input[type="password"]'
            page.fill(password_selector, self.password)
            
            login_button_selector = 'button:has-text("ログインする")'
            page.click(login_button_selector)
            
            # ログイン後のページ遷移を待機
            page.wait_for_load_state('networkidle', timeout=30000)
            
            # ログインに成功したか確認（ダッシュボードまたは注文ページにリダイレクトされているか）
            current_url = page.url
            if 'login' not in current_url:
                self.logger.info("✓ ログインに成功しました")
                self.is_logged_in = True
                page.close()
                return True
            else:
                self.logger.error("✗ ログインに失敗しました")
                page.close()
                return False
                
        except Exception as e:
            raise Exception(f"ログイン処理中にエラーが発生しました: {e}")
    
    def fill_order_form(self, order_group: List[Dict]):
        try:
            page = self.context.new_page()
            self.pages.append(page)
            
            page.goto('https://yiwupassport.jp/order', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            self.logger.info("✓ 注文ページを開きました")
            
            self._fill_order_items(page, order_group)
            return self._confirm_and_submit_order(page)
            
        except Exception as e:
            self.logger.error(f"✗ 注文グループの入力中にエラーが発生しました: {e}")
            raise
    
    def _fill_order_items(self, page: Page, order_group: List[Dict]):
        for idx, order_info in enumerate(order_group, 1):
            item_identifier = order_info.get('ASIN', order_info.get('商品名', f'商品{idx}'))
            self.logger.info(f"  商品{idx}: {item_identifier} を入力中...")
            self._fill_field(page, order_info['商品名'], [f'input[name="item_name{idx}"]'])
            self._fill_field(page, order_info['購入先URL'], [f'input[name="item_url{idx}"]'])
            self._fill_field(page, str(order_info['発注数']), [f'input[name="item_lot{idx}"]'])
            if order_info.get('色・サイズ等指定'):
                self._fill_field(page, order_info['色・サイズ等指定'], [f'textarea[name="item_size{idx}"]'])
            if order_info.get('単価'):
                self._fill_field(page, str(order_info['単価']), [f'input[name="item_price{idx}"]'])
        self.logger.info(f"✓ {len(order_group)}商品の入力が完了しました")
    
    def _confirm_and_submit_order(self, page: Page) -> Optional[str]:
        try:
            # 注文確認ボタンをクリック
            confirm_button_selector = '#btn-confirm'
            page.wait_for_selector(confirm_button_selector, state='visible', timeout=10000)
            page.click(confirm_button_selector)
            self.logger.info("    ✓ 注文確認ボタンをクリックしました")
            
            # モーダルが表示されるまで待機
            modal_selector = '#modal-confirm'
            page.wait_for_selector(modal_selector, state='visible', timeout=10000)
            self.logger.info("    ✓ 確認モーダルが表示されました")
            time.sleep(1)
            
            # 「上記の内容で登録する」ボタンをクリック
            complete_button_selector = '#btn-complete'
            page.wait_for_selector(complete_button_selector, state='visible', timeout=10000)
            page.click(complete_button_selector)
            page.wait_for_load_state('networkidle', timeout=30000)
            self.logger.info("    ✓ 注文が送信されました")

            order_number = self._extract_order_number(page)
            if order_number:
                self.logger.info("    ✓ ご注文番号: %s", order_number)
            else:
                self.logger.warning("    ご注文番号を取得できませんでした（URL: %s）", page.url)

            return order_number
            
        except Exception as e:
            self.logger.error(f"    ✗ 注文確認処理中にエラーが発生しました: {e}")
            raise

    def _extract_order_number(self, page: Page) -> Optional[str]:
        try:
            current_url = page.url or ""
            match = re.search(r"\b(\d{4}-\d{8})\b", current_url)
            if match:
                return match.group(1)

            locator = page.locator("h3:has-text('ご注文番号')").first
            if locator.count() > 0:
                text = locator.inner_text(timeout=3000)
                match = re.search(r"(\d{4}-\d{8})", text)
                if match:
                    return match.group(1)

            html = page.content()
            match = re.search(r"ご注文番号[:：]\s*(\d{4}-\d{8})", html)
            if match:
                return match.group(1)
        except Exception:
            return None
        return None
    
    def _fill_field(self, page: Page, value: str, selectors: List[str]) -> bool:
        for selector in selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    page.wait_for_selector(selector, state='visible', timeout=5000)
                    page.fill(selector, value)
                    return True
            except Exception:
                continue
        
        self.logger.warning(f"  警告: フィールドが見つかりませんでした（値: {value}）")
        return False
    
    def process_orders(self, order_groups: List[List[Dict]]) -> List[OrderGroupResult]:
        if not order_groups:
            self.logger.info("処理する注文がありません")
            return []
        
        self.logger.info("[ステップ3] 注文フォームに自動入力を開始します...")

        self.start_browser()
        if not self.is_logged_in:
            login_success = self.login()
            if not login_success:
                self.logger.error("ログインに失敗したため、処理を中止します")
                return []
        
        total_items = sum(len(group) for group in order_groups)
        self.logger.info(f"{len(order_groups)}グループ（合計{total_items}商品）の注文を処理します...")

        results: List[OrderGroupResult] = []
        
        for i, order_group in enumerate(order_groups, 1):
            self.logger.info(f"[{i}/{len(order_groups)}] グループ処理中...")
            try:
                order_number = self.fill_order_form(order_group)
                results.append(OrderGroupResult(order_group=order_group, order_number=order_number))
            except Exception as e:
                self.logger.warning(f"注文グループの処理をスキップします: {e}")
                results.append(OrderGroupResult(order_group=order_group, order_number=None, error=str(e)))
                continue
            time.sleep(2)
        
        self.logger.info(f"すべての注文フォームへの入力が完了しました")
        self.close_browser()
        self.logger.info("処理が完了しました")
        return results

