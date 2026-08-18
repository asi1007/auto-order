from __future__ import annotations

from unittest.mock import Mock, patch

from domain.value_objects.material_row import MaterialRow
from infrastructure.chatwork_client import ChatworkClient
from usecases.ingest_material_requests import IngestMaterialRequests

_SHEET_URL = "https://test.url"


class TestChatworkClientFetchMessages:
    def test_ルームの直近メッセージを取得する(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = [
            {"message_id": "1", "send_time": 100, "body": "hello", "account": {"name": "徐雪蘭"}}
        ]
        client = ChatworkClient(api_token="token", default_room_id="397092794")

        with patch("infrastructure.chatwork_client.requests.get", return_value=response) as get:
            messages = client.fetch_messages("397092794")

        assert [m["message_id"] for m in messages] == ["1"]
        assert get.call_args[1]["headers"] == {"X-ChatWorkToken": "token"}

    def test_新着がない場合の204を空として扱う(self) -> None:
        client = ChatworkClient(api_token="token", default_room_id="397092794")

        with patch("infrastructure.chatwork_client.requests.get", return_value=Mock(status_code=204)):
            assert client.fetch_messages("397092794") == []


def _usecase(chatwork_messages: list[dict], processed: set[str]) -> tuple[IngestMaterialRequests, Mock, Mock]:
    chatwork_client = Mock()
    chatwork_client.fetch_messages.return_value = chatwork_messages

    packing_repository = Mock()
    packing_repository.set_order_quantities.side_effect = (
        lambda url, quantity_by_row, sheet_name: len(quantity_by_row)
    )
    packing_repository.read_material_rows.return_value = [
        MaterialRow(row_number=26, name="2L特注ダンボール", detail="縦230 mm × 横183 mm × 高さ20mm"),
        MaterialRow(row_number=30, name="OPP袋1", detail="6*13(100个)*普通5丝"),
    ]

    history_repository = Mock()
    history_repository.latest_quantity_by_material.return_value = {"2L特注ダンボール": 3000}

    store = Mock()
    store.is_processed.side_effect = lambda message_id: message_id in processed

    usecase = IngestMaterialRequests(
        chatwork_client=chatwork_client,
        packing_repository=packing_repository,
        history_repository=history_repository,
        store=store,
        room_id="397092794",
        packing_sheet_url=_SHEET_URL,
        packing_sheet_name="使用資材",
    )
    return usecase, packing_repository, store


def _message(message_id: str, body: str) -> dict:
    return {"message_id": message_id, "send_time": 0, "body": body, "account": {"name": "徐雪蘭"}}


class TestIngestMaterialRequests:
    def test_未処理の依頼だけを計画に含める(self) -> None:
        body = "230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。"
        usecase, _, _ = _usecase([_message("old", body), _message("new", body)], processed={"old"})

        plan = usecase.build_plan()

        assert [order.request.message_id for order in plan.orders] == ["new"]

    def test_依頼でない発言は計画に含めない(self) -> None:
        usecase, _, _ = _usecase([_message("1", "納品書をお願いいたします。30*40*50cmです。")], processed=set())

        plan = usecase.build_plan()

        assert plan.orders == ()
        assert plan.pendings == ()

    def test_計画を適用すると発注数を書き込み処理済みにする(self) -> None:
        body = "230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。"
        usecase, packing_repository, store = _usecase([_message("new", body)], processed=set())

        written = usecase.apply(usecase.build_plan())

        assert written == 1
        packing_repository.set_order_quantities.assert_called_once_with(
            _SHEET_URL, {26: 3000}, sheet_name="使用資材"
        )
        store.mark_processed.assert_called_once_with(["new"])

    def test_保留のみの計画では何も書き込まず処理済みにもしない(self) -> None:
        body = "6*13のOPP袋が在庫不足ので、再注文してお願いいたします。"
        usecase, packing_repository, store = _usecase([_message("new", body)], processed=set())

        written = usecase.apply(usecase.build_plan())

        assert written == 0
        packing_repository.set_order_quantities.assert_not_called()
        store.mark_processed.assert_not_called()


class TestIngestMaterialRequestsSeeding:
    def test_過去分のシードでは書き込まず全依頼を処理済みにする(self) -> None:
        usecase, packing_repository, store = _usecase(
            [
                _message("resolved", "230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。"),
                _message("pending", "この商品用の袋が足りなくて、再注文してお願いいたします。"),
            ],
            processed=set(),
        )

        seeded = usecase.mark_all_as_processed(usecase.build_plan())

        assert seeded == 2
        packing_repository.set_order_quantities.assert_not_called()
        assert set(store.mark_processed.call_args[0][0]) == {"resolved", "pending"}


class TestIngestMaterialRequestsSeedingBefore:
    def test_指定日より前の依頼だけを処理済みにする(self) -> None:
        old = {
            "message_id": "old",
            "send_time": 1783500620,  # 2026-07-08
            "body": "230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。",
            "account": {"name": "徐雪蘭"},
        }
        recent = {
            "message_id": "recent",
            "send_time": 1787016420,  # 2026-08-17
            "body": "OPP袋在庫不足分を再注文してお願いいたします。6*13です。",
            "account": {"name": "徐雪蘭"},
        }
        usecase, packing_repository, store = _usecase([old, recent], processed=set())

        seeded = usecase.mark_as_processed_before(usecase.build_plan(), cutoff_epoch=1786800000)

        assert seeded == 1
        assert store.mark_processed.call_args[0][0] == ["old"]
        packing_repository.set_order_quantities.assert_not_called()
