from __future__ import annotations

import pytest

from domain.services.material_matcher import MaterialMatcher
from domain.value_objects.material_request import SizeToken
from domain.value_objects.material_row import MaterialRow


def _token(text: str, *values: float) -> SizeToken:
    return SizeToken(text=text, values=frozenset(values))


@pytest.fixture
def matcher() -> MaterialMatcher:
    rows = [
        MaterialRow(row_number=3, name="A3アクリル段ボール", detail="ダンボールの厚さ1.5mm__箱サイズ（内寸）：縦47cm × 横35cm × 高さ2cm"),
        MaterialRow(row_number=13, name="A4プチプチ", detail="30*35（100个）"),
        MaterialRow(row_number=12, name="B5プチプチ", detail="25*30（100个）"),
        MaterialRow(row_number=21, name="B5量産ダンボール", detail="310*226*23mm"),
        MaterialRow(row_number=24, name="A4特注ダンボール", detail="ダンボールの厚さ1.5mm__箱サイズ（内寸）：縦348mm × 横260mm × 高さ20mm"),
        MaterialRow(row_number=25, name="A5特注ダンボール", detail="ダンボールの厚さ1.5mm__箱サイズ（内寸）：縦260 mm × 横203 mm × 高さ20mm"),
        MaterialRow(row_number=26, name="2L特注ダンボール", detail="ダンボールの厚さ1.5mm__箱サイズ（内寸）：縦230 mm × 横183 mm × 高さ20mm"),
        MaterialRow(row_number=30, name="OPP袋1", detail="6*13(100个)*普通5丝\t"),
        MaterialRow(row_number=35, name="OPP袋6", detail="15*25（100↑）*普通5¾"),
        MaterialRow(row_number=27, name="スチールプレート用袋", detail="10.5x15cm*马卡龙白色*加厚"),
        MaterialRow(row_number=37, name="OPP袋8", detail="32*40（100个j*普通5这"),
        MaterialRow(row_number=40, name="OPP袋11", detail="32*40(100个)*普通5丝"),
    ]
    return MaterialMatcher(rows)

class TestMaterialMatcher:
    def test_mm表記のケースを特注ダンボールに一意に紐づける(self, matcher: MaterialMatcher) -> None:
        match = matcher.match(_token("230*183*20mm", 230, 183, 20), categories=("ダンボール",))

        assert match.is_unique
        assert match.rows[0].name == "2L特注ダンボール"

    def test_カテゴリ語でOPP袋を絞り込む(self, matcher: MaterialMatcher) -> None:
        match = matcher.match(_token("6*13", 6, 13), categories=("OPP", "袋"))

        assert match.is_unique
        assert match.rows[0].name == "OPP袋1"

    def test_詳細の括弧内にある入数を寸法として扱わない(self, matcher: MaterialMatcher) -> None:
        match = matcher.match(_token("30*100", 30, 100), categories=("プチプチ",))

        assert match.rows == ()

    def test_該当する資材がなければ候補を返さない(self, matcher: MaterialMatcher) -> None:
        match = matcher.match(_token("999*888", 999, 888), categories=("ダンボール",))

        assert match.rows == ()
        assert not match.is_unique

    def test_カテゴリ語がなくても寸法だけで特定できる(self, matcher: MaterialMatcher) -> None:
        match = matcher.match(_token("310*226*23MM", 310, 226, 23), categories=())

        assert match.is_unique
        assert match.rows[0].name == "B5量産ダンボール"

    def test_同じ寸法の資材が複数あるときは絞りきらず候補を全て返す(self, matcher: MaterialMatcher) -> None:
        match = matcher.match(_token("32*40", 32, 40), categories=("OPP", "袋"))

        assert not match.is_unique
        assert {row.name for row in match.rows} == {"OPP袋8", "OPP袋11"}

    def test_カテゴリに一致する候補が無ければ絞り込みを諦めて全候補を返す(self, matcher: MaterialMatcher) -> None:
        match = matcher.match(_token("32*40", 32, 40), categories=("プチプチ",))

        assert {row.name for row in match.rows} == {"OPP袋8", "OPP袋11"}

    def test_寸法が近い資材があってもOPP袋を取り違えない(self, matcher: MaterialMatcher) -> None:
        match = matcher.match(_token("15*25", 15, 25), categories=("OPP", "袋"))

        assert match.is_unique
        assert match.rows[0].name == "OPP袋6"
