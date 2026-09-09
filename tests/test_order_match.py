from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from infrastructure.order_automation import (
    SPEC_GROUP_OPTION_SELECTOR,
    MATCH_LABEL_PRODUCT,
    MATCH_LABEL_SPEC,
    MATCH_LABEL_STORE,
    SPEC_OPTION_SELECTOR,
    OrderAutomation,
    SpecMatchRequiredError,
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
    def __init__(
        self,
        matches: dict[str, int],
        spec_options: list[str],
        group_options: list[str] | None = None,
    ) -> None:
        self._matches = matches
        self._spec_options = spec_options
        self._group_options = group_options or []
        self.clicks: list[tuple[str, int]] = []

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self, selector)

    def count_of(self, selector: str) -> int:
        if selector == SPEC_OPTION_SELECTOR:
            return len(self._spec_options)
        if selector == SPEC_GROUP_OPTION_SELECTOR:
            return len(self._group_options)
        for label, count in self._matches.items():
            if label in selector:
                return count
        return 1

    def texts_of(self, selector: str) -> list[str]:
        if selector == SPEC_OPTION_SELECTOR:
            return self._spec_options
        if selector == SPEC_GROUP_OPTION_SELECTOR:
            return self._group_options
        return [""]

    def picked_labels(self) -> list[str]:
        return [
            self.texts_of(sel)[i]
            for sel, i in self.clicks
            if sel in (SPEC_OPTION_SELECTOR, SPEC_GROUP_OPTION_SELECTOR)
        ]

    def clicked_labels(self) -> list[str]:
        return [sel for sel, _ in self.clicks]


@pytest.fixture
def automation() -> OrderAutomation:
    instance = OrderAutomation(headless=True, email="a@example.com", password="pw")
    instance._goto_with_retry = Mock()
    return instance


def _page(
    store: int = 1,
    product: int = 1,
    spec: int = 1,
    options: list[str] | None = None,
    groups: list[str] | None = None,
) -> _FakePage:
    return _FakePage(
        {MATCH_LABEL_STORE: store, MATCH_LABEL_PRODUCT: product, MATCH_LABEL_SPEC: spec},
        options if options is not None else ["9890"],
        groups,
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

    def test_一致しなければ発注せず質問のために止める(self, automation: OrderAutomation) -> None:
        page = _page(options=["赤 M", "赤 L"])
        with patch("infrastructure.order_automation.time.sleep"):
            with pytest.raises(SpecMatchRequiredError) as excinfo:
                automation.match_spec(page, 0, "青 S", asin="B0TEST12345")

        assert excinfo.value.asin == "B0TEST12345"
        assert excinfo.value.desired == "青 S"
        assert excinfo.value.candidates == ["赤 M", "赤 L"]
        assert any("キャンセル" in sel for sel in page.clicked_labels())
        assert not any("確認" in sel for sel in page.clicked_labels())

    def test_止めた規格は質問として記録される(self, automation: OrderAutomation) -> None:
        page = _page(options=["赤 M", "赤 L"])
        with patch("infrastructure.order_automation.time.sleep"):
            with pytest.raises(SpecMatchRequiredError):
                automation.match_spec(page, 0, "青 S", asin="B0TEST12345")

        assert len(automation.pending_spec_questions) == 1
        assert automation.pending_spec_questions[0].asin == "B0TEST12345"

    def test_仕様マッチが出ていなければ何もしない(self, automation: OrderAutomation) -> None:
        page = _page(spec=0)
        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.match_spec(page, 0, "") is False
        assert page.clicks == []


class Test規格が2軸に分かれている場合:
    """1688 の商品によっては款式（内框尺寸）とサイズ（外框尺寸）で選択軸が2本ある。

    仕入情報シートは2行（款式\\nサイズ）で持っており、1行の文字列として
    照合すると必ず外れる。2026-09-08 の A3アクリルフォトフレームで発注が止まった。
    """

    def test_改行で軸ごとに割る(self) -> None:
        assert OrderAutomation._spec_axes("摆挂两用款-直角\nA3（ 内框 297*420mm )厚度3+3mm") == [
            "摆挂两用款-直角",
            "A3（ 内框 297*420mm )厚度3+3mm",
        ]

    def test_1軸なら1件のまま(self) -> None:
        assert OrderAutomation._spec_axes("白色22*8cm硅藻泥垫") == ["白色22*8cm硅藻泥垫"]

    def test_空白行は落とす(self) -> None:
        assert OrderAutomation._spec_axes("摆挂两用款-直角\n\n  \nA3") == ["摆挂两用款-直角", "A3"]

    def test_未指定は空になる(self) -> None:
        assert OrderAutomation._spec_axes("") == []
        assert OrderAutomation._spec_axes(None) == []

    def test_軸ごとに完全一致で選べる(self) -> None:
        groups = ["摆台款-直角", "挂墙款-直角", "摆挂两用款-直角"]
        sizes = ["A4（ 内框 210*297mm )厚度3+3mm", "A3（ 内框 297*420mm )厚度3+3mm"]
        axes = OrderAutomation._spec_axes("摆挂两用款-直角\nA3（ 内框 297*420mm )厚度3+3mm")
        assert OrderAutomation._choose_spec_index(groups, axes[0]) == 2
        assert OrderAutomation._choose_spec_index(sizes, axes[1]) == 1

    def test_款式を取り違えない(self) -> None:
        # 摆台款-直角 と 摆挂两用款-直角 は区切りで割ると「直角」が共通する。
        # 完全一致が1件あるのでそちらが選ばれること
        groups = ["摆台款-直角", "摆挂两用款-直角"]
        assert OrderAutomation._choose_spec_index(groups, "摆挂两用款-直角") == 1
        assert OrderAutomation._choose_spec_index(groups, "摆台款-直角") == 0


class Test2軸のダイアログ操作:
    """_spec_axes / _choose_spec_index の組み合わせではなく、実際に押す順序を見る。

    第1軸（チップ）を押してから第2軸（価格付き行）を押し、最後に確認を押す。
    どちらの軸で外れても、確認を押さずキャンセルして止める。
    """

    COLORS = ["黑色（不含卡纸）", "白色（不含卡纸）", "红木色（不含卡纸）"]
    FRAMES = ["A4(可摆可挂)", "A4(挂墙)", "A3(挂墙)"]

    def test_第1軸と第2軸を順に押して確認する(self, automation: OrderAutomation) -> None:
        page = _page(options=self.COLORS, groups=self.FRAMES)
        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.match_spec(page, 0, "A4(挂墙)\n黑色（不含卡纸）") is True

        assert page.picked_labels() == ["A4(挂墙)", "黑色（不含卡纸）"]
        assert any("確認" in sel for sel in page.clicked_labels())

    def test_第1軸が一致しなければ第2軸に触れず止める(self, automation: OrderAutomation) -> None:
        page = _page(options=self.COLORS, groups=self.FRAMES)
        with patch("infrastructure.order_automation.time.sleep"):
            with pytest.raises(SpecMatchRequiredError) as excinfo:
                automation.match_spec(page, 0, "A2(挂墙)\n黑色（不含卡纸）", asin="B0TEST12345")

        assert excinfo.value.desired == "A2(挂墙)"
        assert excinfo.value.candidates == self.FRAMES
        assert page.picked_labels() == []
        assert not any("確認" in sel for sel in page.clicked_labels())

    def test_第2軸が一致しなければ第1軸を押した後に止める(self, automation: OrderAutomation) -> None:
        page = _page(options=self.COLORS, groups=self.FRAMES)
        with patch("infrastructure.order_automation.time.sleep"):
            with pytest.raises(SpecMatchRequiredError) as excinfo:
                automation.match_spec(page, 0, "A4(挂墙)\n金色（不含卡纸）", asin="B0TEST12345")

        assert excinfo.value.desired == "金色（不含卡纸）"
        assert page.picked_labels() == ["A4(挂墙)"]
        assert not any("確認" in sel for sel in page.clicked_labels())

    def test_1行しか無ければ第1軸は押さない(self, automation: OrderAutomation) -> None:
        page = _page(options=self.COLORS, groups=self.FRAMES)
        with patch("infrastructure.order_automation.time.sleep"):
            assert automation.match_spec(page, 0, "黑色（不含卡纸）") is True

        assert page.picked_labels() == ["黑色（不含卡纸）"]
