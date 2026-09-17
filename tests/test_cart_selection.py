from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from infrastructure.order_automation import CART_SELECT_ALL_SELECTOR, OrderAutomation


class _FakeCheckbox:
    def __init__(self, page: "_FakeCartPage", exists: bool, index: int = 0) -> None:
        self._page = page
        self._exists = exists
        self._index = index

    def nth(self, index: int) -> "_FakeCheckbox":
        return _FakeCheckbox(self._page, self._exists, index)

    @property
    def first(self) -> "_FakeCheckbox":
        return self.nth(0)

    def count(self) -> int:
        return 1 if self._exists else 0

    def get_attribute(self, name: str) -> str | None:
        return "true" if self._page.checked else "false"

    def click(self, timeout: int | None = None) -> None:
        if not self._exists:
            raise TimeoutError("checkbox not found")
        self._page.checked = True


class _FakeCartPage:
    def __init__(self, has_checkbox: bool = True) -> None:
        self.checked = False
        self.selectors: list[str] = []
        self._has_checkbox = has_checkbox

    def locator(self, selector: str) -> _FakeCheckbox:
        self.selectors.append(selector)
        return _FakeCheckbox(self, self._has_checkbox)


@pytest.fixture
def automation() -> OrderAutomation:
    instance = OrderAutomation(headless=True, email="a@example.com", password="pw")
    instance._goto_with_retry = Mock()
    return instance


class Test決済前のカート選択:
    """カートに入れただけでは選択されず「数量合計 0PCS」のまま決済が進まない。

    2026-09-17 の B0GSLDK2DJ（アルミ箔カードカバー 3万個）で 2回連続して
    注文提出がタイムアウトした。他の商品はカート追加時に自動選択されて
    たまたま通っていた。決済の前に必ず選択する。
    """

    def test_決済前にカートの商品を選択する(self, automation: OrderAutomation) -> None:
        page = _FakeCartPage()

        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.select_all_in_cart(page) is True

        assert page.checked is True
        assert page.selectors[0] == CART_SELECT_ALL_SELECTOR

    def test_チェックボックスが無くても落ちない(self, automation: OrderAutomation) -> None:
        page = _FakeCartPage(has_checkbox=False)

        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.select_all_in_cart(page) is False

        assert page.checked is False
