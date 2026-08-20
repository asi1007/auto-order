from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from infrastructure.order_automation import OrderAutomation


class _LateRenderingPage:
    """描画が遅れるSPAの再現。待たずに fill するとタイムアウトする。"""

    def __init__(self) -> None:
        self.awaited_selectors: list[str] = []
        self.filled: dict[str, str] = {}
        self.url = "https://yp.buyer-central.com/manual"

    def wait_for_selector(self, selector: str, timeout: int | None = None):
        self.awaited_selectors.append(selector)
        return Mock()

    def fill(self, selector: str, value: str) -> None:
        if selector not in self.awaited_selectors:
            raise TimeoutError(f"Page.fill: Timeout 30000ms exceeded. waiting for locator({selector})")
        self.filled[selector] = value

    def click(self, selector: str) -> None:
        return None

    def wait_for_load_state(self, state: str, timeout: int | None = None) -> None:
        return None


@pytest.fixture
def automation() -> OrderAutomation:
    instance = OrderAutomation(headless=True, email="a@example.com", password="pw")
    instance._goto_with_retry = Mock()
    return instance


class TestLoginWaitsForForm:
    def test_描画が遅れても入力欄を待ってからログインする(self, automation: OrderAutomation) -> None:
        page = _LateRenderingPage()
        automation.context = Mock()
        automation.context.new_page.return_value = page

        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.login() is True

        assert page.filled['input[type="text"]'] == "a@example.com"
        assert page.filled['input[type="password"]'] == "pw"
        assert automation.is_logged_in
