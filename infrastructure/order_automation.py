from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING
from urllib.parse import urlparse
import time
import logging
import re
import os

from domain.entities.order_group import OrderGroup
from domain.entities.order import Order

if TYPE_CHECKING:
    from playwright.sync_api import Page, Locator

BASE_URL = "https://yp.buyer-central.com"


def sync_playwright():  # pragma: no cover
    from playwright.sync_api import sync_playwright as _sync_playwright

    return _sync_playwright()


class OrderAutomation:
    FIELDS_PER_ROW = 6
    TD_INDEX_STORE_NAME = 0
    TD_INDEX_PRODUCT_NAME = 2
    TD_INDEX_SPEC = 3
    TD_INDEX_URL = 4
    TD_INDEX_QUANTITY = 5
    TD_INDEX_UNIT_PRICE = 6

    def __init__(self, headless: bool = False, email: str = None, password: str = None):
        self.headless = headless
        self.email = email
        self.password = password
        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None
        self.is_logged_in = False
        self.logger = logging.getLogger(__name__)
        if not self.email or not self.password:
            self.logger.error("エラー: ログイン情報が設定されていません")
            self.logger.error(".envファイルにYIWUPASSPORT_EMAILとYIWUPASSPORT_PASSWORDを設定してください")
            raise Exception("ログイン情報が設定されていません")

    @classmethod
    def from_env(cls, headless: bool = False) -> "OrderAutomation":
        email = os.getenv("YIWUPASSPORT_EMAIL")
        password = os.getenv("YIWUPASSPORT_PASSWORD")
        return cls(headless=headless, email=email, password=password)

    def start_browser(self):
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=500,
            )
            self.context = self.browser.new_context(
                viewport={"width": 1280, "height": 900}
            )
            self.logger.info("✓ ブラウザを起動しました")
        except Exception as e:
            raise Exception(f"ブラウザの起動に失敗しました: {e}")

    def close_browser(self):
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.logger.info("✓ ブラウザを閉じました")
        except Exception as e:
            self.logger.error(f"ブラウザのクローズ中にエラーが発生しました: {e}")

    def _goto_with_retry(self, url: str, max_retries: int = 3) -> None:
        for attempt in range(1, max_retries + 1):
            try:
                self.page.goto(url, timeout=30000, wait_until="domcontentloaded")
                self.page.wait_for_load_state("networkidle", timeout=30000)
                return
            except Exception as e:
                self.logger.warning(
                    "ページ遷移リトライ %s/%s: %s（URL: %s）", attempt, max_retries, e, url
                )
                if attempt == max_retries:
                    raise
                time.sleep(2)

    def login(self) -> bool:
        if not self.email or not self.password:
            raise Exception("ログイン情報が設定されていません")

        try:
            self.logger.info("YP Buyer Centralにログインしています...")

            self.page = self.context.new_page()
            self._goto_with_retry(f"{BASE_URL}/login")

            self.page.fill('input[type="text"]', self.email)
            self.page.fill('input[type="password"]', self.password)
            self.page.click('button:has-text("ログイン")')
            self.page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)

            self._goto_with_retry(f"{BASE_URL}/manual")
            time.sleep(1)

            if "/login" not in self.page.url:
                self.logger.info("✓ ログインに成功しました")
                self.is_logged_in = True
                return True

            self.logger.error("✗ ログインに失敗しました")
            return False

        except Exception as e:
            raise Exception(f"ログイン処理中にエラーが発生しました: {e}")

    def fill_order_form(self, order_group: List[Order]) -> Optional[str]:
        try:
            self._goto_with_retry(f"{BASE_URL}/manual")
            time.sleep(1)
            self.logger.info("✓ 手動注文ページを開きました")

            self._fill_order_items(self.page, order_group)
            return self._confirm_and_submit_order(self.page)

        except Exception as e:
            self.logger.error(f"✗ 注文グループの入力中にエラーが発生しました: {e}")
            raise

    def _fill_order_items(self, page: Page, order_group: List[Order]):
        for idx, order_info in enumerate(order_group, 1):
            item_identifier = order_info.asin or order_info.product_name or f"商品{idx}"
            self.logger.info(
                "  商品%s: %s を入力中...（数量: %s）",
                idx,
                item_identifier,
                order_info.order_quantity,
            )

            page.click('button:has-text("商品を追加")')
            time.sleep(1)

            rows = page.locator("tr")
            data_row = rows.last
            tds = data_row.locator("td")

            store_name = self._extract_store_name(order_info.purchase_url)
            self._fill_td_input(tds.nth(self.TD_INDEX_STORE_NAME), store_name)
            self._fill_td_input(tds.nth(self.TD_INDEX_PRODUCT_NAME), order_info.product_name)
            if order_info.color_size_spec:
                self._fill_td_input(tds.nth(self.TD_INDEX_SPEC), order_info.color_size_spec)
            self._fill_td_input(tds.nth(self.TD_INDEX_URL), order_info.purchase_url)
            self._fill_td_input(tds.nth(self.TD_INDEX_QUANTITY), str(order_info.order_quantity))
            if order_info.unit_price_for_form:
                self._fill_td_input(tds.nth(self.TD_INDEX_UNIT_PRICE), order_info.unit_price_for_form)

        self.logger.info(f"✓ {len(order_group)}商品の入力が完了しました")

    def _fill_td_input(self, td: Locator, value: str) -> bool:
        try:
            input_elem = td.locator("input, textarea").first
            if input_elem.count() > 0:
                input_elem.fill(value)
                return True
        except Exception as e:
            self.logger.warning(f"  警告: フィールドへの入力に失敗しました（値: {value}, エラー: {e}）")
        return False

    def _click_dialog_submit(self, page: Page) -> None:
        dialog = page.locator(".q-dialog")
        dialog.wait_for(state="visible", timeout=10000)
        dialog_submit_btn = dialog.locator('button:has-text("注文提出")')
        dialog_submit_btn.wait_for(state="visible", timeout=10000)
        dialog_submit_btn.click()
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)
        self.logger.info("    ✓ 注文が送信されました")

    def _confirm_and_submit_order(self, page: Page) -> Optional[str]:
        try:
            # ステップ1: フォームページの「注文提出」→ 確認ページまたはダイアログへ遷移
            submit_btn = page.locator('button:has-text("注文提出")')
            submit_btn.wait_for(state="visible", timeout=10000)
            submit_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(3)
            self.logger.info("    ✓ 注文提出ボタンをクリックしました")

            # ダイアログが既に表示されているか確認
            dialog = page.locator(".q-dialog")
            if dialog.count() > 0 and dialog.is_visible():
                self.logger.info("    ✓ 確認ダイアログが表示されました（直接）")
                self._click_dialog_submit(page)
            else:
                # ステップ2: 確認ページの「注文提出」→ 確認ダイアログ表示
                self.logger.info("    ✓ 注文確認ページに遷移しました")
                submit_btn_confirm = page.locator('button:has-text("注文提出")')
                submit_btn_confirm.wait_for(state="visible", timeout=10000)
                submit_btn_confirm.click()
                time.sleep(2)
                self.logger.info("    ✓ 確認ダイアログが表示されました")

                # ステップ3: ダイアログ内の「注文提出」→ 注文確定
                self._click_dialog_submit(page)

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
            order_number = self._wait_for_order_number_on_page(page)
            if order_number:
                return order_number

            order_number = self._get_latest_order_number_from_history(page)
            if order_number:
                return order_number
        except Exception:
            return None
        return None

    def _wait_for_order_number_on_page(self, page: Page) -> Optional[str]:
        try:
            locator = page.locator("text=注文番号").first
            locator.wait_for(state="visible", timeout=10000)
            time.sleep(1)

            html = page.content()
            match = re.search(r"(P\d{9}YP\d+)", html)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    def _get_latest_order_number_from_history(self, page: Page) -> Optional[str]:
        try:
            page.goto(f"{BASE_URL}/order/list", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=30000)

            locator = page.locator("text=注文番号").first
            locator.wait_for(state="visible", timeout=10000)
            time.sleep(1)

            html = page.content()
            matches = re.findall(r"(P\d{9}YP\d+)", html)
            if matches:
                return matches[0]
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_store_name(purchase_url: str) -> str:
        try:
            parsed = urlparse(purchase_url)
            hostname = parsed.hostname or ""
            hostname = hostname.replace("www.", "")
            return hostname if hostname else "不明"
        except Exception:
            return "不明"

    def process_orders(self, order_groups: List[List[Order]]) -> List[OrderGroup]:
        if not order_groups:
            self.logger.info("処理する注文がありません")
            return []

        self.logger.info("[ステップ3] 注文フォームに自動入力を開始します...")

        self.start_browser()
        if not self.is_logged_in:
            login_success = self.login()
            if not login_success:
                self.logger.error("ログインに失敗したため、処理を中止します")
                self.close_browser()
                return []

        total_items = sum(len(group) for group in order_groups)
        self.logger.info(f"{len(order_groups)}グループ（合計{total_items}商品）の注文を処理します...")

        results: List[OrderGroup] = []

        for i, order_group in enumerate(order_groups, 1):
            self.logger.info(f"[{i}/{len(order_groups)}] グループ処理中...")
            try:
                order_number = self.fill_order_form(order_group)
                results.append(OrderGroup(order_group=order_group, order_number=order_number))
            except Exception as e:
                self.logger.warning(f"注文グループの処理をスキップします: {e}")
                results.append(OrderGroup(order_group=order_group, order_number=None, error=str(e)))
                continue
            time.sleep(2)

        self.logger.info("すべての注文フォームへの入力が完了しました")
        self.close_browser()
        self.logger.info("処理が完了しました")
        return results
