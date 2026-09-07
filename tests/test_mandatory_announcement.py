from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from infrastructure.order_automation import (
    ANNOUNCEMENT_BUTTON_SELECTOR,
    MAX_ANNOUNCEMENT_DISMISSALS,
    OrderAutomation,
)


class _AnnouncementButtons:
    def __init__(self, page: "_AnnouncementPage") -> None:
        self._page = page

    def count(self) -> int:
        return self._page.pending

    @property
    def first(self) -> "_AnnouncementButtons":
        return self

    def click(self) -> None:
        self._page.clicked += 1
        if self._page.closeable:
            self._page.pending -= 1


class _AnnouncementPage:
    def __init__(self, pending: int, closeable: bool = True) -> None:
        self.pending = pending
        self.closeable = closeable
        self.clicked = 0
        self.selectors: list[str] = []

    def locator(self, selector: str) -> _AnnouncementButtons:
        self.selectors.append(selector)
        return _AnnouncementButtons(self)


@pytest.fixture
def automation() -> OrderAutomation:
    instance = OrderAutomation(headless=True, email="a@example.com", password="pw")
    instance._goto_with_retry = Mock()
    return instance


class TestDismissMandatoryAnnouncements:
    def test_必読お知らせが出ていれば既読にして閉じる(self, automation: OrderAutomation) -> None:
        page = _AnnouncementPage(pending=1)

        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.dismiss_mandatory_announcements(page) == 1

        assert page.clicked == 1
        assert page.pending == 0
        assert page.selectors[0] == ANNOUNCEMENT_BUTTON_SELECTOR

    def test_お知らせが複数あれば全て閉じる(self, automation: OrderAutomation) -> None:
        page = _AnnouncementPage(pending=3)

        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.dismiss_mandatory_announcements(page) == 3

        assert page.pending == 0

    def test_お知らせが無ければ何もクリックしない(self, automation: OrderAutomation) -> None:
        page = _AnnouncementPage(pending=0)

        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.dismiss_mandatory_announcements(page) == 0

        assert page.clicked == 0

    def test_閉じられなくても無限ループしない(self, automation: OrderAutomation) -> None:
        page = _AnnouncementPage(pending=1, closeable=False)

        with patch("infrastructure.order_automation.time.sleep"):
            automation.dismiss_mandatory_announcements(page)

        assert page.clicked == MAX_ANNOUNCEMENT_DISMISSALS


class TestLoginDismissesAnnouncements:
    def test_ログイン直後に必読お知らせを閉じる(self, automation: OrderAutomation) -> None:
        page = _AnnouncementPage(pending=1)
        page.url = "https://yp.buyer-central.com/manual"
        page.wait_for_selector = Mock()
        page.fill = Mock()
        page.click = Mock()
        page.wait_for_load_state = Mock()
        automation.context = Mock()
        automation.context.new_page.return_value = page

        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.login() is True

        assert page.clicked == 1
