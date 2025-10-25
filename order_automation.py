"""
Playwrightを使用してイーウーパスポートの注文フォームに自動入力するモジュール
"""

from playwright.sync_api import sync_playwright, Page, Browser
from typing import List, Dict
import time


class OrderAutomation:
    """イーウーパスポートの注文自動化クラス"""
    
    def __init__(self, headless: bool = False, email: str = None, password: str = None):
        """
        初期化
        
        Args:
            headless: ヘッドレスモードで実行するか（デフォルト: False）
            email: イーウーパスポートのログインメールアドレス
            password: イーウーパスポートのログインパスワード
        """
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
        """ブラウザを閉じる"""
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
        """
        イーウーパスポートにログイン
        
        Returns:
            bool: ログインに成功したかどうか
        """
        if not self.email or not self.password:
            raise Exception("ログイン情報が設定されていません")
        
        try:
            print("\nイーウーパスポートにログインしています...")
            
            # ログインページを開く
            page = self.context.new_page()
            page.goto('https://yiwupassport.jp/login', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=30000)
            
            # メールアドレスを入力
            email_selector = 'input[type="text"]'
            page.fill(email_selector, self.email)
            print(f"  ✓ メールアドレスを入力しました")
            
            # パスワードを入力
            password_selector = 'input[type="password"]'
            page.fill(password_selector, self.password)
            print(f"  ✓ パスワードを入力しました")
            
            # ログインボタンをクリック
            login_button_selector = 'button:has-text("ログインする")'
            page.click(login_button_selector)
            print(f"  ✓ ログインボタンをクリックしました")
            
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
        """
        注文フォームに複数商品の情報を入力（商品1〜5）
        
        Args:
            order_group: 注文情報の辞書のリスト（最大5件）
        """
        try:
            # 新しいタブを開く
            page = self.context.new_page()
            self.pages.append(page)
            
            # グループ内の全ASINを表示
            asins = [order['ASIN'] for order in order_group]
            purchase_url = order_group[0]['購入先URL']
            
            print(f"\n--- 注文フォームを開いています ---")
            print(f"  購入先URL: {purchase_url}")
            print(f"  商品数: {len(order_group)}件 ({', '.join(asins)})")
            
            # イーウーパスポートの注文ページに移動
            page.goto('https://yiwupassport.jp/order', timeout=30000)
            
            # ページが完全に読み込まれるまで待機
            page.wait_for_load_state('networkidle', timeout=30000)
            
            print(f"✓ 注文ページを開きました")
            
            # 各商品をフォームに入力（商品1〜5）
            for idx, order_info in enumerate(order_group, 1):
                print(f"\n  商品{idx}: {order_info['ASIN']} を入力中...")
                
                # 商品名を入力
                if self._fill_field(page, order_info['商品名'], 
                                   [f'input[name="item_name{idx}"]']):
                    print(f"    ✓ 商品名: {order_info['商品名']}")
                
                # 商品URLを入力
                if self._fill_field(page, order_info['購入先URL'], 
                                   [f'input[name="item_url{idx}"]']):
                    print(f"    ✓ 商品URL: {order_info['購入先URL']}")
                
                # 色・サイズ等指定を入力
                if order_info['色・サイズ等指定']:
                    if self._fill_field(page, order_info['色・サイズ等指定'], 
                                       [f'textarea[name="item_size{idx}"]']):
                        print(f"    ✓ 色・サイズ等指定: {order_info['色・サイズ等指定']}")
                
                # 発注数を入力
                if self._fill_field(page, str(order_info['発注数']), 
                                   [f'input[name="item_lot{idx}"]']):
                    print(f"    ✓ 発注数: {order_info['発注数']}")
                
                # 単価を入力
                if order_info['単価']:
                    if self._fill_field(page, str(order_info['単価']), 
                                       [f'input[name="item_price{idx}"]']):
                        print(f"    ✓ 単価: {order_info['単価']}")
            
            print(f"\n✓ {len(order_group)}商品の入力が完了しました")
            print("  注意: 注文確認ボタンは自動でクリックされません。内容を確認して手動で発注してください。")
            
            # 少し待機（ユーザーが確認できるように）
            time.sleep(1)
            
        except Exception as e:
            print(f"✗ 注文グループの入力中にエラーが発生しました: {e}")
            raise
    
    def _fill_field(self, page: Page, value: str, selectors: List[str]) -> bool:
        """
        複数のセレクタを試して入力フィールドに値を入力
        
        Args:
            page: Playwrightのページオブジェクト
            value: 入力する値
            selectors: 試すセレクタのリスト
            
        Returns:
            bool: 入力に成功したかどうか
        """
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
        """
        複数の注文グループを処理
        
        Args:
            order_groups: 注文情報のグループのリスト（各グループは最大5商品）
        """
        if not order_groups:
            print("処理する注文がありません")
            return
        
        try:
            self.start_browser()
            
            # ログイン処理
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
            print(f"開いているタブ数: {len(self.pages)}")
            print(f"各タブで内容を確認し、問題なければ手動で注文確認ボタンをクリックしてください")
            print(f"{'='*60}")
            
            # ユーザーが確認できるようにブラウザを開いたまま待機
            # 注: 実際の運用では、この待機を削除するか調整してください
            print("\n確認後、スクリプトを終了するには Ctrl+C を押してください...")
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

