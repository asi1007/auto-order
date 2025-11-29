"""
Playwrightを使用してイーウーパスポートの注文フォームに自動入力するモジュール
"""

from playwright.sync_api import sync_playwright, Page, Browser
from typing import List, Dict
import time


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
            print("✓ ブラウザを起動しました")
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
            print("✓ ブラウザを閉じました")
        except Exception as e:
            print(f"ブラウザのクローズ中にエラーが発生しました: {e}")
    
    def login(self):
        if not self.email or not self.password:
            raise Exception("ログイン情報が設定されていません")
        
        try:
            print("\nイーウーパスポートにログインしています...")
            
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
                print("✓ ログインに成功しました")
                self.is_logged_in = True
                page.close()
                return True
            else:
                print("✗ ログインに失敗しました")
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
            print(f"✓ 注文ページを開きました")
            
            # 各商品をフォームに入力
            self._fill_order_items(page, order_group)
            
            # 注文確認ボタンをクリックして送信
            self._confirm_and_submit_order(page)
            
        except Exception as e:
            print(f"✗ 注文グループの入力中にエラーが発生しました: {e}")
            raise
    
    def _fill_order_items(self, page: Page, order_group: List[Dict]):
        for idx, order_info in enumerate(order_group, 1):
            print(f"\n  商品{idx}: {order_info['ASIN']} を入力中...")
            self._fill_field(page, order_info['商品名'], [f'input[name="item_name{idx}"]'])
            self._fill_field(page, order_info['購入先URL'], [f'input[name="item_url{idx}"]'])
            self._fill_field(page, str(order_info['発注数']), [f'input[name="item_lot{idx}"]'])
            if order_info['色・サイズ等指定']:
                self._fill_field(page, order_info['色・サイズ等指定'], [f'textarea[name="item_size{idx}"]'])
            self._fill_field(page, str(order_info['単価']), [f'input[name="item_price{idx}"]'])
        print(f"\n✓ {len(order_group)}商品の入力が完了しました")
    
    def _confirm_and_submit_order(self, page: Page):
        try:
            # 注文確認ボタンをクリック
            confirm_button_selector = '#btn-confirm'
            page.wait_for_selector(confirm_button_selector, state='visible', timeout=10000)
            page.click(confirm_button_selector)
            print("    ✓ 注文確認ボタンをクリックしました")
            
            # モーダルが表示されるまで待機
            modal_selector = '#modal-confirm'
            page.wait_for_selector(modal_selector, state='visible', timeout=10000)
            print("    ✓ 確認モーダルが表示されました")
            
            # 少し待機（モーダルのアニメーション完了を待つ）
            time.sleep(1)
            
            # 「上記の内容で登録する」ボタンをクリック
            complete_button_selector = '#btn-complete'
            page.wait_for_selector(complete_button_selector, state='visible', timeout=10000)
            page.click(complete_button_selector)
            print("    ✓ 「上記の内容で登録する」ボタンをクリックしました")
            
            # フォーム送信後のページ遷移を待機
            page.wait_for_load_state('networkidle', timeout=30000)
            print("    ✓ 注文が送信されました")
            
        except Exception as e:
            print(f"    ✗ 注文確認処理中にエラーが発生しました: {e}")
            print("    手動で注文確認ボタンをクリックしてください")
            raise
    
    def _fill_field(self, page: Page, value: str, selectors: List[str]) -> bool:
        for selector in selectors:
            try:
                # 要素が存在するか確認
                element = page.query_selector(selector)
                if element:
                    # 要素が見えるまで待機
                    page.wait_for_selector(selector, state='visible', timeout=5000)
                    # 入力
                    page.fill(selector, value)
                    return True
            except Exception:
                continue
        
        # どのセレクタでも見つからなかった場合
        print(f"  警告: フィールドが見つかりませんでした（値: {value}）")
        return False
    
    def process_orders(self, order_groups: List[List[Dict]]):
        if not order_groups:
            print("処理する注文がありません")
            return
        
        try:
            self.start_browser()
            if not self.is_logged_in:
                login_success = self.login()
                if not login_success:
                    print("ログインに失敗したため、処理を中止します")
                    return
            
            total_items = sum(len(group) for group in order_groups)
            print(f"\n{len(order_groups)}グループ（合計{total_items}商品）の注文を処理します...")
            
            for i, order_group in enumerate(order_groups, 1):
                print(f"\n[{i}/{len(order_groups)}] グループ処理中...")
                try:
                    self.fill_order_form(order_group)
                except Exception as e:
                    print(f"注文グループの処理をスキップします: {e}")
                    continue
                
                # 次のグループまで少し待機
                time.sleep(2)
            
            print(f"\n{'='*60}")
            print(f"すべての注文フォームへの入力が完了しました")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n終了します...")
            
        finally:
            self.close_browser()


def automate_orders(order_groups: List[List[Dict]], headless: bool = False, email: str = None, password: str = None):
    """
    注文の自動化を実行する便利関数
    
    Args:
        order_groups: 注文情報のグループのリスト（各グループは最大5商品）
        headless: ヘッドレスモードで実行するか
        email: イーウーパスポートのログインメールアドレス
        password: イーウーパスポートのログインパスワード
    """
    automation = OrderAutomation(headless=headless, email=email, password=password)
    automation.process_orders(order_groups)

