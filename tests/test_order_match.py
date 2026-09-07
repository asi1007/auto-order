from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from infrastructure.order_automation import (
    MATCH_LABEL_PRODUCT,
    MATCH_LABEL_SPEC,
    MATCH_LABEL_STORE,
    SPEC_OPTION_SELECTOR,
    OrderAutomation,
)


class _FakeLocator:
    def __init__(self, page: "_FakePage", selector: str, index: int = 0) -> None:
        self._page = page
        self._selector = selector
        self._index = index

    def nth(self, index: int) -> "_FakeLocator":
        return _FakeLocator(self._page, self._selector, index)

    @property
    def first(self) -> "_FakeLocator":
        return self.nth(0)

    @property
    def last(self) -> "_FakeLocator":
        return self.nth(max(self._page.count_of(self._selector) - 1, 0))

    def count(self) -> int:
        return self._page.count_of(self._selector)

    def wait_for(self, state: str = "visible", timeout: int | None = None) -> None:
        if self._page.count_of(self._selector) <= self._index:
            raise TimeoutError(f"not visible: {self._selector}")

    def text_content(self) -> str:
        return self._page.texts_of(self._selector)[self._index]

    def click(self) -> None:
        self._page.clicks.append((self._selector, self._index))


class _FakePage:
    def __init__(self, matches: dict[str, int], spec_options: list[str]) -> None:
        self._matches = matches
        self._spec_options = spec_options
        self.clicks: list[tuple[str, int]] = []

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self, selector)

    def count_of(self, selector: str) -> int:
        if selector == SPEC_OPTION_SELECTOR:
            return len(self._spec_options)
        for label, count in self._matches.items():
            if label in selector:
                return count
        return 1

    def texts_of(self, selector: str) -> list[str]:
        if selector == SPEC_OPTION_SELECTOR:
            return self._spec_options
        return [""]

    def clicked_labels(self) -> list[str]:
        return [sel for sel, _ in self.clicks]


@pytest.fixture
def automation() -> OrderAutomation:
    instance = OrderAutomation(headless=True, email="a@example.com", password="pw")
    instance._goto_with_retry = Mock()
    return instance


def _page(store: int = 1, product: int = 1, spec: int = 1, options: list[str] | None = None) -> _FakePage:
    return _FakePage(
        {MATCH_LABEL_STORE: store, MATCH_LABEL_PRODUCT: product, MATCH_LABEL_SPEC: spec},
        options if options is not None else ["9890"],
    )


class TestClickMatch:
    def test_マッチが出ていればクリックする(self, automation: OrderAutomation) -> None:
        page = _page()
        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.click_match(page, MATCH_LABEL_STORE, 0) is True
        assert any(MATCH_LABEL_STORE in sel for sel in page.clicked_labels())

    def test_マッチが出ていなければ落ちずにスキップする(self, automation: OrderAutomation) -> None:
        page = _page(store=0)
        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.click_match(page, MATCH_LABEL_STORE, 0) is False
        assert page.clicks == []


class TestChooseSpecIndex:
    def test_候補が1つなら選ぶ(self) -> None:
        assert OrderAutomation._choose_spec_index(["9890"], "") == 0

    def test_候補が複数なら完全一致だけ選ぶ(self) -> None:
        labels = ["赤 M", "赤 L", "青 M"]
        assert OrderAutomation._choose_spec_index(labels, "赤 L") == 1

    def test_候補が複数で完全一致が無ければ選ばない(self) -> None:
        labels = ["赤 M", "赤 L"]
        assert OrderAutomation._choose_spec_index(labels, "赤") is None

    def test_部分一致では選ばない(self) -> None:
        labels = ["40倍 LED付き 黒", "40倍 LED付き 銀"]
        assert OrderAutomation._choose_spec_index(labels, "40倍 LED付き") is None

    def test_区切りで分割した一区画と完全一致すれば選ぶ(self) -> None:
        labels = ["画刷-1号【白毛】-尼龙毛", "画刷-2号【白毛】-尼龙毛"]
        assert OrderAutomation._choose_spec_index(labels, "1号【白毛】") == 0

    def test_区画一致でも1号は11号を巻き込まない(self) -> None:
        labels = ["画刷-11号【白毛】-尼龙毛", "画刷-1号【白毛】-尼龙毛"]
        assert OrderAutomation._choose_spec_index(labels, "1号【白毛】") == 1

    def test_区画一致の候補が複数なら選ばない(self) -> None:
        labels = ["A-赤-綿", "B-赤-麻"]
        assert OrderAutomation._choose_spec_index(labels, "赤") is None


class TestMatchSpec:
    def test_候補が1つなら選んで確認する(self, automation: OrderAutomation) -> None:
        page = _page(options=["9890"])
        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.match_spec(page, 0, "") is True
        assert any("確認" in sel for sel in page.clicked_labels())

    def test_一致しなければキャンセルして進む(self, automation: OrderAutomation) -> None:
        page = _page(options=["赤 M", "赤 L"])
        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.match_spec(page, 0, "青 S") is False
        assert any("キャンセル" in sel for sel in page.clicked_labels())
        assert not any("確認" in sel for sel in page.clicked_labels())

    def test_仕様マッチが出ていなければ何もしない(self, automation: OrderAutomation) -> None:
        page = _page(spec=0)
        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.match_spec(page, 0, "") is False
        assert page.clicks == []
