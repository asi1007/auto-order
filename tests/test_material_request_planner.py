from __future__ import annotations

import pytest

from domain.services.material_matcher import MaterialMatcher
from domain.services.material_request_parser import MaterialRequestParser
from domain.services.material_request_planner import MaterialRequestPlanner
from domain.value_objects.material_row import MaterialRow

_ROWS = [
    MaterialRow(row_number=13, name="A4プチプチ", detail="30*35（100个）"),
    MaterialRow(row_number=26, name="2L特注ダンボール", detail="縦230 mm × 横183 mm × 高さ20mm"),
    MaterialRow(row_number=30, name="OPP袋1", detail="6*13(100个)*普通5丝"),
    MaterialRow(row_number=37, name="OPP袋8", detail="32*40（100个j*普通5这"),
    MaterialRow(row_number=40, name="OPP袋11", detail="32*40(100个)*普通5丝"),
]
_QUANTITIES = {"A4プチプチ": 10000, "2L特注ダンボール": 3000, "OPP袋8": 20000}


@pytest.fixture
def planner() -> MaterialRequestPlanner:
    return MaterialRequestPlanner(matcher=MaterialMatcher(_ROWS), quantity_by_material=_QUANTITIES)


def _request(body: str, message_id: str = "1"):
    request = MaterialRequestParser().parse(message_id=message_id, sent_at=0, body=body)
    assert request is not None
    return request


class TestMaterialRequestPlanner:
    def test_特定できた資材に過去の発注実績の数量を割り当てる(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan([_request("230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。")])

        assert len(plan.orders) == 1
        assert plan.orders[0].material.name == "2L特注ダンボール"
        assert plan.orders[0].quantity == 3000
        assert plan.orders[0].material.row_number == 26
        assert plan.pendings == ()

    def test_発注実績のない資材は数量を決められず保留する(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan([_request("OPP袋在庫不足分を再注文してお願いいたします。6*13です。")])

        assert plan.orders == ()
        assert plan.pendings[0].reason == "発注実績なし"
        assert plan.pendings[0].candidates[0].name == "OPP袋1"

    def test_サイズ表記のない依頼は資材を特定できず保留する(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan([_request("この商品用の袋が足りなくて、再注文してお願いいたします。")])

        assert plan.orders == ()
        assert plan.pendings[0].reason == "サイズ表記なし"
        assert plan.pendings[0].size_token is None

    def test_同じ寸法の資材が複数あれば保留する(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan([_request("OPP袋が在庫不足ので再注文してお願いいたします。32*40です。")])

        assert plan.orders == ()
        assert plan.pendings[0].reason == "候補が複数"
        assert len(plan.pendings[0].candidates) == 2

    def test_該当する資材がなければ保留する(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan([_request("999*888のケースが在庫不足ので、再注文してお願いいたします。")])

        assert plan.pendings[0].reason == "候補なし"

    def test_全て確定した依頼だけを処理済みにできる(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan(
            [
                _request("230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。", message_id="resolved"),
                _request("6*13のOPP袋が在庫不足ので、再注文してお願いいたします。", message_id="pending"),
            ]
        )

        assert plan.resolved_message_ids == ("resolved",)

    def test_一部だけ特定できた依頼は処理済みにしない(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan(
            [
                _request(
                    "在庫不足の分、再注文してお願いいたします。\nケース230*183*20mm\nケース999*888*20mm",
                    message_id="partial",
                )
            ]
        )

        assert len(plan.orders) == 1
        assert len(plan.pendings) == 1
        assert plan.resolved_message_ids == ()

    def test_同じ資材が複数の依頼で重なったら数量をまとめない(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan(
            [
                _request("230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。", message_id="a"),
                _request("230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。", message_id="b"),
            ]
        )

        assert plan.quantity_by_row == {26: 3000}


class TestIngestPlanSeeding:
    def test_保留も含めた全ての依頼のメッセージIDを返す(self, planner: MaterialRequestPlanner) -> None:
        plan = planner.plan(
            [
                _request("230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。", message_id="resolved"),
                _request("この商品用の袋が足りなくて、再注文してお願いいたします。", message_id="pending"),
            ]
        )

        assert set(plan.all_message_ids) == {"resolved", "pending"}


_LOT_ROWS = [
    MaterialRow(row_number=13, name="A4プチプチ", detail="30*35（100个）", lot_size=100),
    MaterialRow(row_number=26, name="2L特注ダンボール", detail="縦230 mm × 横183 mm × 高さ20mm", lot_size=1),
    MaterialRow(row_number=27, name="半端ロット資材", detail="11*22", lot_size=1000),
]


class TestMaterialRequestPlannerLotSize:
    def test_発注数はロット数に換算して割り当てる(self) -> None:
        planner = MaterialRequestPlanner(
            matcher=MaterialMatcher(_LOT_ROWS),
            quantity_by_material={"A4プチプチ": 10000},
        )

        plan = planner.plan([_request("30*35のプチプチ袋が在庫なくて、再注文してお願いいたします。")])

        assert plan.orders[0].quantity == 100
        assert plan.orders[0].piece_count == 10000

    def test_ロットサイズが1なら個数がそのまま発注数になる(self) -> None:
        planner = MaterialRequestPlanner(
            matcher=MaterialMatcher(_LOT_ROWS),
            quantity_by_material={"2L特注ダンボール": 3000},
        )

        plan = planner.plan([_request("230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。")])

        assert plan.orders[0].quantity == 3000

    def test_ロット数に割り切れない実績は保留する(self) -> None:
        planner = MaterialRequestPlanner(
            matcher=MaterialMatcher(_LOT_ROWS),
            quantity_by_material={"半端ロット資材": 2500},
        )

        plan = planner.plan([_request("11*22の袋が在庫不足ので、再注文してお願いいたします。")])

        assert plan.orders == ()
        assert plan.pendings[0].reason == "ロット数に割り切れない"


class TestMaterialRequestPlannerOverrides:
    def test_発注実績が無くても指定した発注数を使う(self) -> None:
        planner = MaterialRequestPlanner(
            matcher=MaterialMatcher(_ROWS),
            quantity_by_material={},
            order_quantity_overrides={"OPP袋1": 300},
        )

        plan = planner.plan([_request("6*13のOPP袋が在庫不足ので、再注文してお願いいたします。")])

        assert plan.orders[0].quantity == 300
        assert plan.pendings == ()

    def test_指定した発注数は発注実績より優先する(self) -> None:
        planner = MaterialRequestPlanner(
            matcher=MaterialMatcher(_ROWS),
            quantity_by_material={"2L特注ダンボール": 3000},
            order_quantity_overrides={"2L特注ダンボール": 500},
        )

        plan = planner.plan([_request("230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。")])

        assert plan.orders[0].quantity == 500
