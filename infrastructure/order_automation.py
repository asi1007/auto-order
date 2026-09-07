from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING
from urllib.parse import urlparse
import time
import logging
import re
import os

from domain.entities.order_group import OrderGroup
from domain.entities.order import Order
from domain.value_objects.balance import Balance

if TYPE_CHECKING:
    from playwright.sync_api import Page, Locator

BASE_URL = "https://yp.buyer-central.com"
LOGIN_FORM_TIMEOUT_MS = 60000
ANNOUNCEMENT_BUTTON_LABEL = "既読にする"
ANNOUNCEMENT_BUTTON_SELECTOR = f'div.q-dialog:visible button:has-text("{ANNOUNCEMENT_BUTTON_LABEL}")'
MAX_ANNOUNCEMENT_DISMISSALS = 5

# YP の手動注文フォームの「マッチ」は button ではなく div。
# 押すと 1688 から店舗名・商品名・規格を引いてフォームへ同期する（倉庫からの依頼で 2026-09-04 に追加）。
MATCH_LABEL_STORE = "店舗名マッチ"
MATCH_LABEL_PRODUCT = "商品名マッチ"
MATCH_LABEL_SPEC = "仕様マッチ"
MATCH_WAIT_MS = 5000
# 規格の候補行。行に click ハンドラが付いているのでラベルの span を押せば選択される。
SPEC_OPTION_SELECTOR = "div.border-line.grid.cursor-pointer span.col-span-2"
SPEC_CONFIRM_LABEL = "確認"
SPEC_CANCEL_LABEL = "キャンセル"


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

    def _fill_login_form(self) -> None:
        # QuasarのSPAで描画が遅れると fill が即タイムアウトする。入力欄の出現を待ってから入れる
        for selector, value in (
            ('input[type="text"]', self.email),
            ('input[type="password"]', self.password),
        ):
            self.page.wait_for_selector(selector, timeout=LOGIN_FORM_TIMEOUT_MS)
            self.page.fill(selector, value)

    def login(self) -> bool:
        if not self.email or not self.password:
            raise Exception("ログイン情報が設定されていません")

        try:
            self.logger.info("YP Buyer Centralにログインしています...")

            self.page = self.context.new_page()
            self._goto_with_retry(f"{BASE_URL}/login")

            self._fill_login_form()
            self.page.click('button:has-text("ログイン")')
            self.page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)

            self._goto_with_retry(f"{BASE_URL}/manual")
            time.sleep(1)

            if "/login" not in self.page.url:
                self.logger.info("✓ ログインに成功しました")
                self.is_logged_in = True
                self.dismiss_mandatory_announcements()
                return True

            self.logger.error("✗ ログインに失敗しました")
            return False

        except Exception as e:
            raise Exception(f"ログイン処理中にエラーが発生しました: {e}")

    def dismiss_mandatory_announcements(self, page: Optional["Page"] = None) -> int:
        target = page or self.page
        dismissed = 0
        for _ in range(MAX_ANNOUNCEMENT_DISMISSALS):
            button = target.locator(ANNOUNCEMENT_BUTTON_SELECTOR)
            if button.count() == 0:
                break
            button.first.click()
            dismissed += 1
            time.sleep(1)
        if dismissed:
            self.logger.info("必読お知らせを %s 件「%s」で閉じました", dismissed, ANNOUNCEMENT_BUTTON_LABEL)
        return dismissed

    def click_match(self, page: "Page", label: str, idx: int) -> bool:
        locator = page.locator(f'div:text-is("{label}")').nth(idx)
        try:
            locator.wait_for(state="visible", timeout=MATCH_WAIT_MS)
        except Exception:
            self.logger.warning("「%s」が表示されないためスキップしました（商品%s）", label, idx + 1)
            return False
        locator.click()
        time.sleep(1)
        self.logger.info("    ✓ 「%s」を実行しました（商品%s）", label, idx + 1)
        return True

    @staticmethod
    def _spec_segments(label: str) -> List[str]:
        return [seg.strip() for seg in re.split(r"[-－/|]", label) if seg.strip()]

    @staticmethod
    def _choose_spec_index(labels: List[str], desired: str) -> Optional[int]:
        if len(labels) == 1:
            return 0
        target = (desired or "").strip()
        if not target:
            return None

        exact = [i for i, label in enumerate(labels) if label.strip() == target]
        if len(exact) == 1:
            return exact[0]

        # 仕入情報シートは 1688 の規格名の一部だけを持つことが多い
        # （例: シート「1号【白毛】」/ 1688「画刷-1号【白毛】-尼龙毛」）。
        # 区切りで割った一区画との完全一致だけを許す。部分一致は 1号 が 11号 を巻き込むため使わない。
        segmented = [
            i for i, label in enumerate(labels) if target in OrderAutomation._spec_segments(label)
        ]
        if len(segmented) == 1:
            return segmented[0]
        return None

    def _cancel_spec_dialog(self, page: "Page") -> None:
        try:
            page.locator(f'button:has-text("{SPEC_CANCEL_LABEL}")').last.click()
            time.sleep(1)
        except Exception as e:
            self.logger.warning("仕様ダイアログを閉じられませんでした: %s", e)

    def match_spec(self, page: "Page", idx: int, desired_spec: str) -> bool:
        if not self.click_match(page, MATCH_LABEL_SPEC, idx):
            return False

        options = page.locator(SPEC_OPTION_SELECTOR)
        try:
            options.first.wait_for(state="visible", timeout=MATCH_WAIT_MS)
        except Exception:
            self.logger.warning("規格の候補が出ませんでした（商品%s）。テキストのまま進めます", idx + 1)
            self._cancel_spec_dialog(page)
            return False

        labels = [(options.nth(i).text_content() or "").strip() for i in range(options.count())]
        target = self._choose_spec_index(labels, desired_spec)
        if target is None:
            self.logger.warning(
                "仕様「%s」に一致する規格がありません（候補: %s）。テキストのまま進めます",
                desired_spec,
                labels,
            )
            self._cancel_spec_dialog(page)
            return False

        options.nth(target).click()
        time.sleep(1)
        page.locator(f'button:has-text("{SPEC_CONFIRM_LABEL}")').last.click()
        time.sleep(2)
        self.logger.info("    ✓ 規格「%s」を紐付けました（商品%s）", labels[target], idx + 1)
        return True

    def _parse_jpy_balance(self, text: str) -> int:
        if not text:
            return 0
        cleaned = re.sub(r"[^\d]", "", text)
        return int(cleaned) if cleaned else 0

    def fetch_balance(self) -> Balance:
        self._goto_with_retry(f"{BASE_URL}/home")
        time.sleep(2)

        cny_locator = self.page.locator("text=/CNY.*元/")
        jpy_locator = self.page.locator("text=/JPY.*円/")

        cny_text = cny_locator.first.text_content().strip() if cny_locator.count() > 0 else ""
        jpy_text = jpy_locator.first.text_content().strip() if jpy_locator.count() > 0 else ""

        return Balance.from_texts(cny_text, jpy_text)

    def _log_balance(self, label: str = "発注後") -> None:
        try:
            balance = self.fetch_balance()
            self.logger.info("💰 %s残高: CNY %s 元 / JPY %s 円", label, f"{balance.cny:,.2f}", f"{balance.jpy:,.0f}")
        except Exception as e:
            self.logger.warning("残高取得に失敗しました: %s", e)

    def convert_jpy_to_cny(self) -> None:
        try:
            self.logger.info("日本円残高を確認しています...")
            self._goto_with_retry(f"{BASE_URL}/home")
            time.sleep(2)

            jpy_locator = self.page.locator("text=/JPY.*円/")
            if jpy_locator.count() == 0:
                self.logger.info("日本円残高が見つかりません。両替をスキップします")
                return

            jpy_text = jpy_locator.first.text_content()
            jpy_balance = self._parse_jpy_balance(jpy_text)

            if jpy_balance <= 0:
                self.logger.info("日本円残高が0円のため、両替をスキップします")
                return

            self.logger.info("日本円残高: %s円 → 全額を中国元に両替します", jpy_balance)

            spinbutton = self.page.get_by_role("spinbutton")
            spinbutton.wait_for(state="visible", timeout=10000)
            spinbutton.fill(str(jpy_balance))
            time.sleep(1)

            submit_btn = self.page.locator('button:has-text("振替を実行する")')
            submit_btn.wait_for(state="visible", timeout=10000)
            submit_btn.click()
            time.sleep(2)

            dialog = self.page.get_by_role("dialog")
            dialog.wait_for(state="visible", timeout=10000)
            self.logger.info("確認ダイアログが表示されました。承認します...")
            confirm_btn = dialog.locator('button:has-text("確定")')
            confirm_btn.wait_for(state="visible", timeout=10000)
            confirm_btn.click()
            self.page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)

            self.logger.info("✓ 両替が完了しました（%s円 → 中国元）", jpy_balance)

        except Exception as e:
            self.logger.warning("両替処理中にエラーが発生しました（発注処理は継続します）: %s", e)

    def clear_cart(self) -> None:
        # 過去の発注失敗で残ったゾンビ商品がカートにあると、次回発注時に巻き込まれて
        # 全体が失敗するため、発注フロー開始前にカートを空にする。
        try:
            self.logger.info("発注前にカートをクリアしています...")
            self._goto_with_retry(f"{BASE_URL}/goods/cart")
            time.sleep(2)

            # 全選択チェックボックス（ページ上の最初のチェックボックスを採用）
            all_checkbox = self.page.locator('input[type="checkbox"]').first
            if all_checkbox.count() == 0:
                self.logger.info("✓ カートは空です（チェックボックスなし）")
                return

            try:
                all_checkbox.check(force=True, timeout=5000)
            except Exception:
                # チェックボックスが既に選択済みの場合などはスルー
                pass
            time.sleep(0.5)

            # 削除ボタン候補（テキスト揺れに備えて複数）
            for label in ("削除", "全削除", "一括削除", "选中删除", "删除"):
                btn = self.page.locator(f'button:has-text("{label}")')
                if btn.count() == 0:
                    continue
                try:
                    btn.last.click(timeout=3000)
                except Exception:
                    continue

                # 確認ダイアログが出る場合は確定
                try:
                    dialog = self.page.locator(".q-dialog")
                    dialog.wait_for(state="visible", timeout=5000)
                    for dlg_label in ("確定", "OK", "確認", "はい", "确定"):
                        dlg_btn = dialog.locator(f'button:has-text("{dlg_label}")')
                        if dlg_btn.count() > 0:
                            dlg_btn.first.click()
                            break
                except Exception:
                    pass

                self.page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(2)
                self.logger.info("✓ カートをクリアしました（削除ボタン: %s）", label)
                return

            self.logger.warning("カート削除ボタンが見つかりませんでした（カートに残留商品がある場合は手動で削除してください）")
        except Exception as e:
            self.logger.warning("カートクリア処理中にエラー（発注処理は継続します）: %s", e)

    def _reset_order_form(self, page: Page) -> None:
        reset_btn = page.locator('button:has-text("リセット")')
        if reset_btn.count() > 0 and reset_btn.is_visible():
            reset_btn.click()
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)
            self.logger.info("  ✓ フォームをリセットしました")

    def fill_order_form(self, order_group: List[Order]) -> Optional[str]:
        try:
            # 提出前に /order/list の最新注文番号をスナップショット。
            # 提出後に取得した番号がこれと同じなら「成立していない」と判定するために使う。
            pre_submit_latest = self._snapshot_latest_order_number(self.page)
            if pre_submit_latest:
                self.logger.debug("  提出前 最新注文番号: %s", pre_submit_latest)

            self._goto_with_retry(f"{BASE_URL}/manual")
            time.sleep(1)
            self._reset_order_form(self.page)
            self.logger.info("✓ 手動注文ページを開きました")

            self._fill_order_items(self.page, order_group)
            return self._confirm_and_submit_order(self.page, pre_submit_latest)

        except Exception as e:
            self.logger.error(f"✗ 注文グループの入力中にエラーが発生しました: {e}")
            self._dump_page_for_debug(self.page, reason="fill_failure")
            raise

    # YP の新UI (2026-06-28 以降) フィールド placeholder
    PLACEHOLDER_STORE_NAME = "店舗名を入力してください"
    PLACEHOLDER_URL = "商品URL入力"
    PLACEHOLDER_PRODUCT_NAME = "商品名入力"
    PLACEHOLDER_QUANTITY = "数量"
    PLACEHOLDER_UNIT_PRICE = "単価"
    PLACEHOLDER_SPEC_NAME = "商品仕様入力"
    PLACEHOLDER_SPEC_NOTE = "仕様備考の入力"

    def _fill_order_items(self, page: Page, order_group: List[Order]):
        # 新UI構造: 1店舗 × N商品（同一URLグループでも各ASINを別 商品 ブロックとして扱う）。
        # 店舗名は1つだけ（idx=0で1回入力）。
        # 2件目以降は「+商品」ボタンでブロックを追加し、URL/商品名/数量/単価/仕様備考を nth(idx) で埋める。
        for idx, order_info in enumerate(order_group):
            item_identifier = order_info.asin or order_info.product_name or f"商品{idx+1}"
            self.logger.info(
                "  商品%s: %s を入力中...（数量: %s）",
                idx + 1,
                item_identifier,
                order_info.order_quantity,
            )

            if idx == 0:
                store_name = self._extract_store_name(order_info.purchase_url)
                self._fill_placeholder_nth(page, self.PLACEHOLDER_STORE_NAME, 0, store_name)
            else:
                self._add_product_row(page)

            self._fill_placeholder_nth(page, self.PLACEHOLDER_URL, idx, order_info.purchase_url)
            self._fill_placeholder_nth(page, self.PLACEHOLDER_PRODUCT_NAME, idx, order_info.product_name)
            # 新UI（2026-06〜）では「商品仕様」が必須項目になった。
            # color_size_spec があればそれを入れ、空なら product_name を流用してフォーム送信を通す。
            spec_value = order_info.color_size_spec or order_info.product_name
            self._fill_placeholder_nth(page, self.PLACEHOLDER_SPEC_NAME, idx, spec_value)
            self._fill_placeholder_nth(page, self.PLACEHOLDER_QUANTITY, idx, str(order_info.order_quantity))
            if order_info.unit_price_for_form:
                self._fill_placeholder_nth(
                    page, self.PLACEHOLDER_UNIT_PRICE, idx, str(order_info.unit_price_for_form)
                )
            if order_info.color_size_spec:
                self._fill_placeholder_nth(
                    page, self.PLACEHOLDER_SPEC_NOTE, idx, order_info.color_size_spec, required=False
                )

            self._match_order_item(page, idx, order_info)

        self.logger.info(f"✓ {len(order_group)}商品の入力が完了しました")

    def _match_order_item(self, page: "Page", idx: int, order_info: Order) -> None:
        # 倉庫（買付担当）が 1688 の店舗・商品・規格を特定できるようにマッチさせる。
        # 失敗しても発注は止めない。テキスト入力のまま提出される。
        if idx == 0:
            self.click_match(page, MATCH_LABEL_STORE, 0)
        self.click_match(page, MATCH_LABEL_PRODUCT, idx)
        if self.match_spec(page, idx, order_info.color_size_spec or ""):
            self._restore_unit_price(page, idx, order_info)

    def _restore_unit_price(self, page: "Page", idx: int, order_info: Order) -> None:
        # 規格を紐付けると YP が 1688 の価格で単価を上書きする。
        # 残高確認・仕入管理は仕入情報シートの単価で組んであるため、こちらへ戻す。
        if not order_info.unit_price_for_form:
            return
        expected = str(order_info.unit_price_for_form)
        actual = self._read_placeholder_nth(page, self.PLACEHOLDER_UNIT_PRICE, idx)
        if actual and actual != expected:
            self.logger.warning(
                "規格紐付けで単価が %s 元 に変わりました（シートは %s 元）。シートの値に戻します",
                actual,
                expected,
            )
        self._fill_placeholder_nth(page, self.PLACEHOLDER_UNIT_PRICE, idx, expected)

    def _read_placeholder_nth(self, page: "Page", placeholder: str, idx: int) -> str:
        try:
            return page.locator(f'input[placeholder="{placeholder}"]').nth(idx).input_value().strip()
        except Exception:
            return ""

    def _fill_placeholder_nth(
        self, page: Page, placeholder: str, idx: int, value: str, *, required: bool = True
    ) -> bool:
        # YP 新UI (2026-06〜) では Quasar の q-field 内部 input が hidden 状態のまま
        # 表示されることがある。visible 待ちでは取れないので attached を待ってから
        # スクロールして force=True で fill する。
        loc = page.locator(f'input[placeholder="{placeholder}"]').nth(idx)
        try:
            loc.wait_for(state="attached", timeout=10000)
            try:
                loc.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass
            loc.fill(value, force=True, timeout=5000)
            time.sleep(0.3)
            return True
        except Exception as e:
            if required:
                raise Exception(
                    f"フィールド[{placeholder}] (nth={idx}) への入力失敗: {e}"
                ) from e
            self.logger.debug(
                "  optional フィールド[%s] (nth=%d) は attached でないためスキップ", placeholder, idx
            )
            return False

    def _add_product_row(self, page: Page) -> None:
        """同一店舗グループに「+商品」ボタンで行を追加する。

        新UI (2026-06 以降) の DOM 構造:
          <img class="w-5 cursor-pointer" ...>   # 削除ボタン
          <span class="bg-warning ...">商品1</span>  # ラベル（"商品" + 番号）
          <img class="w-6 h-6 cursor-pointer" ...>   # ← ここが「+商品」ボタン
        旧UIは text()="商品" だったが、新UIは "商品1" "商品2" のように番号付きになったため
        starts-with で前方一致にする。last() で最新の商品ブロックの「+」を選ぶ。
        """
        plus_btn = page.locator(
            'xpath=(//span[contains(@class, "bg-warning") and starts-with(normalize-space(.), "商品")]'
            "/following-sibling::img[contains(@class, 'cursor-pointer')])[last()]"
        )
        plus_btn.wait_for(state="attached", timeout=10000)
        try:
            plus_btn.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        plus_btn.click(force=True, timeout=5000)
        time.sleep(1.5)  # 新商品ブロックが DOM に追加されるのを待つ

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

    def _confirm_and_submit_order(self, page: Page, pre_submit_latest: Optional[str] = None) -> Optional[str]:
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

            # 提出後の注文番号取得は YP 注文一覧への反映遅延に耐えるためリトライする。
            # 「取れた番号が提出前と同じ」= まだ新規注文が反映されていない可能性があるので、
            # 最大 max_retry_seconds まで interval_seconds ごとに再取得を試みる。
            max_retry_seconds = 60
            interval_seconds = 5
            elapsed = 0
            order_number: Optional[str] = None
            while True:
                order_number = self._extract_order_number(page)
                if order_number and (not pre_submit_latest or order_number != pre_submit_latest):
                    break
                if elapsed >= max_retry_seconds:
                    break
                self.logger.debug(
                    "注文番号リスト反映待ち → %s秒後にリトライ（現在=%s / 提出前=%s / elapsed=%ds）",
                    interval_seconds, order_number, pre_submit_latest, elapsed,
                )
                time.sleep(interval_seconds)
                elapsed += interval_seconds

            if not order_number:
                self.logger.warning("    ご注文番号を取得できませんでした（URL: %s）", page.url)
                return None
            if pre_submit_latest and order_number == pre_submit_latest:
                # 上限まで待っても新規番号がリスト反映されなかった → 実際に成立していない可能性が高い
                self.logger.error(
                    "    ✗ 注文番号 %s が提出前の最新番号と同一です（%ds待機後も更新なし）。注文は成立していない可能性が高いです。",
                    order_number, max_retry_seconds,
                )
                self._dump_page_for_debug(page, reason="order_not_created")
                return None
            self.logger.info("    ✓ ご注文番号: %s（取得までelapsed=%ds）", order_number, elapsed)
            return order_number

        except Exception as e:
            self.logger.error(f"    ✗ 注文確認処理中にエラーが発生しました: {e}")
            self._dump_page_for_debug(page, reason="submit_failure")
            raise

    def _snapshot_latest_order_number(self, page: Page) -> Optional[str]:
        # 提出前に /order/list の最新注文番号を取得しておく。失敗しても発注フローには影響させない。
        # この後 fill_order_form 内で /manual に goto し直すので、元URLへ戻す処理は不要。
        try:
            page.goto(f"{BASE_URL}/order/list", timeout=30000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            try:
                page.wait_for_function(
                    f"() => /{self.ORDER_NUMBER_PATTERN}/.test(document.body.innerText)",
                    timeout=10000,
                )
            except Exception:
                return None
            matches = re.findall(self.ORDER_NUMBER_PATTERN, page.content())
            return matches[0] if matches else None
        except Exception:
            return None

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
            self.logger.warning("    デバッグ用ページダンプを保存: %s.html / .png (URL: %s)", prefix, page.url)
        except Exception as e:
            self.logger.debug("ページダンプ保存に失敗: %s", e)

    @staticmethod
    def _extract_store_name(purchase_url: str) -> str:
        # purchase_url が http(s):// で始まらない場合（例:「星球彩印」のような店舗名直書き）は
        # そのまま店舗名として扱う。
        if not purchase_url:
            return "不明"
        if not purchase_url.lower().startswith(("http://", "https://")):
            return purchase_url.strip()
        try:
            parsed = urlparse(purchase_url)
            hostname = parsed.hostname or ""
            hostname = hostname.replace("www.", "")
            return hostname if hostname else "不明"
        except Exception:
            return "不明"

    # YP 側で 1セッション（≒1ブラウザセッション or 短時間内）あたり 2件程度しか成立しない
    # レート制限がある挙動を 2026-07-21, 2026-07-26 の実行で 2回連続確認済み。
    # 対策: この件数ごとにブラウザを閉じて再ログインし、セッションをリフレッシュする。
    GROUPS_PER_SESSION = 2

    def _refresh_session(self) -> bool:
        self.logger.info("🔄 セッションリフレッシュ: ログアウト → クッキークリア → 再ログイン")
        # 1. YP に対して明示的なログアウト（画面上のログアウトボタン、または /logout URL）
        try:
            if self.page:
                try:
                    logout_btn = self.page.locator('button:has-text("ログアウト")').first
                    if logout_btn.count() > 0:
                        logout_btn.click(force=True, timeout=3000)
                        time.sleep(2)
                        self.logger.info("  ✓ ログアウトボタンをクリック")
                except Exception:
                    pass
                try:
                    self.page.goto(f"{BASE_URL}/logout", timeout=10000, wait_until="domcontentloaded")
                    time.sleep(2)
                    self.logger.info("  ✓ /logout URL に遷移")
                except Exception:
                    pass
        except Exception as e:
            self.logger.debug(f"ログアウト試行時のエラー（継続）: {e}")

        # 2. context の cookies を明示的にクリア（次の new context でも念のため）
        try:
            if self.context:
                self.context.clear_cookies()
                self.logger.info("  ✓ Cookies をクリア")
        except Exception:
            pass

        # 3. ブラウザ完全終了
        try:
            self.close_browser()
        except Exception as e:
            self.logger.warning("close_browser でエラー（継続します）: %s", e)

        # インスタンス状態を初期化
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_logged_in = False

        self.start_browser()
        if not self.login():
            self.logger.error("再ログインに失敗しました")
            return False
        self.clear_cart()
        return True

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

        self.clear_cart()
        self.convert_jpy_to_cny()
        # 発注前残高をログに残す。発注後残高との差分計算の起点として使う。
        # ※ 実消費 = 記録合計 + YP側手数料/送料 で差が出るのは仕様。
        self._log_balance("発注前")

        total_items = sum(len(group) for group in order_groups)
        self.logger.info(f"{len(order_groups)}グループ（合計{total_items}商品）の注文を処理します...")

        results: List[OrderGroup] = []
        groups_since_refresh = 0

        for i, order_group in enumerate(order_groups, 1):
            # レート制限回避: GROUPS_PER_SESSION 件ごとにセッションを再構築
            if groups_since_refresh >= self.GROUPS_PER_SESSION:
                if not self._refresh_session():
                    self.logger.error("セッションリフレッシュに失敗したため、以降の処理を中止します")
                    for remaining in order_groups[i-1:]:
                        results.append(OrderGroup(order_group=remaining, order_number=None, error="session refresh failed"))
                    break
                groups_since_refresh = 0

            self.logger.info(f"[{i}/{len(order_groups)}] グループ処理中...")
            try:
                order_number = self.fill_order_form(order_group)
            except Exception as e:
                self.logger.warning(f"注文グループの処理をスキップします: {e}")
                results.append(OrderGroup(order_group=order_group, order_number=None, error=str(e)))
                groups_since_refresh += 1
                continue

            # 【重要】未成立検知時の自動リトライは無効化した（2026-07-31）。
            # 理由: `_confirm_and_submit_order` が None を返すのは以下2ケース：
            #   (a) 提出後の注文番号が提出前と同じ (リスト反映遅延の疑い、内部で60秒リトライ済み)
            #   (b) そもそも注文番号が取れなかった（実は成立している可能性あり、None として区別できない）
            # (b) のケースで自動リトライすると二重発注リスクがあるため、
            # 未成立と判定されたグループは YP で人が確認する運用に統一する。
            # ※ GROUPS_PER_SESSION ごとの定期リフレッシュは残す（安全側）。
            if order_number is None:
                self.logger.warning(
                    "    ⚠ 未成立と判定されました。YP注文一覧で実際に成立していないか手動確認を推奨。"
                    "自動リトライはしません（二重発注リスク回避）"
                )
            groups_since_refresh += 1

            results.append(OrderGroup(order_group=order_group, order_number=order_number))
            time.sleep(2)

        self.logger.info("すべての注文フォームへの入力が完了しました")
        self._log_balance()
        self.close_browser()
        self.logger.info("処理が完了しました")
        return results
