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
            self._dump_page_for_debug(self.page, reason="fill_failure")
            raise

    # YP の新UI (2026-05〜) フィールド placeholder
    PLACEHOLDER_STORE_NAME = "店舗名を入力してください"
    PLACEHOLDER_URL = "製品のURLを入力してください。"
    PLACEHOLDER_PRODUCT_NAME = "商品名を入力してください"
    PLACEHOLDER_QUANTITY = "数量"
    PLACEHOLDER_UNIT_PRICE = "単価"
    PLACEHOLDER_SPEC_NOTE = "仕様備考"

    def _fill_order_items(self, page: Page, order_group: List[Order]):
        for idx, order_info in enumerate(order_group):
            item_identifier = order_info.asin or order_info.product_name or f"商品{idx+1}"
            self.logger.info(
                "  商品%s: %s を入力中...（数量: %s）",
                idx + 1,
                item_identifier,
                order_info.order_quantity,
            )

            if idx > 0:
                self._add_product_row(page)

            store_name = self._extract_store_name(order_info.purchase_url)
            self._fill_placeholder_nth(page, self.PLACEHOLDER_STORE_NAME, idx, store_name)
            self._fill_placeholder_nth(page, self.PLACEHOLDER_URL, idx, order_info.purchase_url)
            self._fill_placeholder_nth(page, self.PLACEHOLDER_PRODUCT_NAME, idx, order_info.product_name)
            self._fill_placeholder_nth(page, self.PLACEHOLDER_QUANTITY, idx, str(order_info.order_quantity))
            if order_info.unit_price_for_form:
                self._fill_placeholder_nth(
                    page, self.PLACEHOLDER_UNIT_PRICE, idx, str(order_info.unit_price_for_form)
                )
            if order_info.color_size_spec:
                self._fill_placeholder_nth(
                    page, self.PLACEHOLDER_SPEC_NOTE, idx, order_info.color_size_spec, required=False
                )

        self.logger.info(f"✓ {len(order_group)}商品の入力が完了しました")

    def _fill_placeholder_nth(
        self, page: Page, placeholder: str, idx: int, value: str, *, required: bool = True
    ) -> bool:
        loc = page.locator(f'input[placeholder="{placeholder}"]').nth(idx)
        try:
            loc.wait_for(state="visible", timeout=10000)
            loc.fill(value)
            time.sleep(0.3)
            return True
        except Exception as e:
            if required:
                raise Exception(
                    f"フィールド[{placeholder}] (nth={idx}) への入力失敗: {e}"
                ) from e
            self.logger.debug(
                "  optional フィールド[%s] (nth=%d) は visible でないためスキップ", placeholder, idx
            )
            return False

    def _add_product_row(self, page: Page) -> None:
        """同一店舗グループに「+商品」ボタンで行を追加する。"""
        plus_btn = page.locator(
            'xpath=(//span[contains(@class, "bg-warning") and normalize-space(text())="商品"]'
            "/following-sibling::img[contains(@class, 'cursor-pointer')])[1]"
        ).last
        plus_btn.wait_for(state="visible", timeout=10000)
        plus_btn.click()
        time.sleep(1)

    def _click_dialog_confirm(self, page: Page) -> None:
        """Quasar 確認ダイアログの確定ボタンを押す。複数候補テキストを試す。"""
        dialog = page.locator(".q-dialog")
        dialog.wait_for(state="visible", timeout=10000)
        for txt in ("確定", "OK", "確認", "決済", "提出", "送信", "はい"):
            btn = dialog.locator(f'button:has-text("{txt}")')
            if btn.count() > 0:
                btn.first.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(3)
                self.logger.info("    ✓ 注文が送信されました（dialog button: %s）", txt)
                return
        raise Exception("確認ダイアログ内に確定ボタンが見つかりませんでした")

    def _confirm_and_submit_order(self, page: Page) -> Optional[str]:
        """新UIフロー（2026-05〜）:
        /manual → カートに追加 → /goods/cart → 決済 → /goods/order-confirm → 注文提出 → 注文番号取得。
        """
        try:
            cart_add_btn = page.locator('button:has-text("カートに追加")').first
            cart_add_btn.wait_for(state="visible", timeout=10000)
            cart_add_btn.click()
            try:
                page.wait_for_url(f"{BASE_URL}/goods/cart", timeout=15000)
            except Exception:
                page.goto(f"{BASE_URL}/goods/cart", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
            self.logger.info("    ✓ カートに追加しました（→ /goods/cart）")

            checkout_btn = page.locator('button:has-text("決済")').last
            checkout_btn.wait_for(state="visible", timeout=10000)
            checkout_btn.click()
            try:
                page.wait_for_url("**/goods/order-confirm**", timeout=15000)
            except Exception:
                pass
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
            self.logger.info("    ✓ 決済 → 注文確認画面へ遷移（%s）", page.url)

            submit_btn = page.locator('button:has-text("注文提出")').last
            submit_btn.wait_for(state="visible", timeout=10000)
            submit_btn.click()
            time.sleep(2)
            self.logger.info("    ✓ 注文提出ボタンをクリックしました")

            # 確認ダイアログが出る場合のみ確定。出なければ既に注文成立 (success page or list)。
            try:
                self._click_dialog_confirm(page)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(2)
                self.logger.info("    ✓ 注文が送信されました（dialog なし、直接成立）")

            order_number = self._extract_order_number(page)
            if order_number:
                self.logger.info("    ✓ ご注文番号: %s", order_number)
            else:
                self.logger.warning("    ご注文番号を取得できませんでした（URL: %s）", page.url)
            return order_number

        except Exception as e:
            self.logger.error(f"    ✗ 注文確認処理中にエラーが発生しました: {e}")
            self._dump_page_for_debug(page, reason="submit_failure")
            raise

    # YP の注文番号フォーマット:
    #   - 旧: P260226013YP806（P + 9桁 + YP + 数字）
    #   - 新: Y0806-260513008（Y + 会員ID + ハイフン + 日付6桁 + 連番3桁）
    # 両方マッチさせる（YP 側 UI 移行期に旧形式が残る可能性に備える）
    ORDER_NUMBER_PATTERN = r"(Y\d+-\d{6,12}|P\d{6,12}YP\d+)"

    def _extract_order_number(self, page: Page) -> Optional[str]:
        try:
            order_number = self._wait_for_order_number_on_page(page)
            if order_number:
                return order_number

            order_number = self._get_latest_order_number_from_history(page)
            if order_number:
                return order_number

            self._dump_page_for_debug(page, reason="order_number_not_found")
        except Exception:
            return None
        return None

    def _wait_for_order_number_on_page(self, page: Page) -> Optional[str]:
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        try:
            page.wait_for_function(
                f"() => /{self.ORDER_NUMBER_PATTERN}/.test(document.body.innerText)",
                timeout=10000,
            )
        except Exception:
            return None

        match = re.search(self.ORDER_NUMBER_PATTERN, page.content())
        return match.group(1) if match else None

    def _get_latest_order_number_from_history(self, page: Page) -> Optional[str]:
        try:
            page.goto(f"{BASE_URL}/order/list", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_function(
                f"() => /{self.ORDER_NUMBER_PATTERN}/.test(document.body.innerText)",
                timeout=15000,
            )

            matches = re.findall(self.ORDER_NUMBER_PATTERN, page.content())
            if matches:
                return matches[0]
        except Exception:
            return None
        return None

    def _dump_page_for_debug(self, page: Page, reason: str) -> None:
        try:
            debug_dir = os.path.join(os.getcwd(), "logs", "debug")
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            prefix = os.path.join(debug_dir, f"{timestamp}_{reason}")
            with open(f"{prefix}.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            page.screenshot(path=f"{prefix}.png", full_page=True)
            self.logger.warning(
                "    デバッグ用ページダンプを保存: %s.html / .png (URL: %s)",
                prefix, page.url,
            )
        except Exception as e:
            self.logger.debug("ページダンプ保存に失敗: %s", e)

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
