from __future__ import annotations

import pytest

from domain.value_objects.packing_materials_sheet import PackingMaterialsSheet
from order_packing_materials import convert_packing_materials_to_order_format


_HEADER = [
    "資材名称", "発注数", "ロットサイズ", "URL", "商品名", "詳細", "価格",
    "chatwork文章", "chatwork添付",
]


def _values(message: str, attachment: str) -> list[list[str]]:
    return [
        [""] * len(_HEADER),
        _HEADER,
        ["アクリル説明書", "30000", "10000", "星球彩印", "アクリル説明書",
         "サイズ91mm*55mm両面白黒印刷157ｇ紙1万枚", "300", message, attachment],
    ]


class TestChatwork列の読み取り:
    """資材の入稿データ（説明書のデザイン）は Chatwork で倉庫へ送る必要がある。

    商品側（仕入情報シート）と同じく chatwork文章 / chatwork添付 を持たせ、
    発注時に添付ごと飛ばす。列が無い古いシートでも壊れないこと。
    """

    def test_chatwork列を読み取る(self) -> None:
        sheet = PackingMaterialsSheet.from_values(
            _values("入稿データです", "https://drive.google.com/file/d/ABC123/view")
        )

        item = sheet.items[0]
        assert item.chatwork_message == "入稿データです"
        assert item.chatwork_attachment == "https://drive.google.com/file/d/ABC123/view"

    def test_chatwork列が無いシートでも読める(self) -> None:
        header = _HEADER[:-2]
        values = [
            [""] * len(header),
            header,
            ["OPP袋8", "500", "100", "https://detail.1688.com/offer/1.html", "opp袋", "32*40", "7.5"],
        ]

        sheet = PackingMaterialsSheet.from_values(values)

        assert sheet.items[0].chatwork_message == ""
        assert sheet.items[0].chatwork_attachment == ""

    def test_空欄なら空文字になる(self) -> None:
        sheet = PackingMaterialsSheet.from_values(_values("", ""))

        assert sheet.items[0].chatwork_message == ""
        assert sheet.items[0].chatwork_attachment == ""


class TestOrderへの引き継ぎ:
    def test_発注データにchatwork情報を引き継ぐ(self) -> None:
        sheet = PackingMaterialsSheet.from_values(
            _values("入稿データです", "https://drive.google.com/file/d/ABC123/view")
        )

        order = convert_packing_materials_to_order_format(sheet.items[0])

        assert order.chatwork_message == "入稿データです"
        assert order.chatwork_attachment == "https://drive.google.com/file/d/ABC123/view"

    def test_chatwork情報が無ければ空のまま(self) -> None:
        sheet = PackingMaterialsSheet.from_values(_values("", ""))

        order = convert_packing_materials_to_order_format(sheet.items[0])

        assert order.chatwork_message == ""
        assert order.chatwork_attachment == ""


class _SpyChatworkClient:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_notifications_for_order_groups(self, order_groups) -> None:
        for group in order_groups:
            for order in group:
                message = str(order.chatwork_message).strip()
                attachment = str(order.chatwork_attachment).strip()
                if not message and not attachment:
                    continue
                self.sent.append((message, attachment))


class _Result:
    def __init__(self, order_group, order_number):
        self.order_group = order_group
        self.order_number = order_number


class Test入稿データの送信:
    def _order(self, message: str, attachment: str):
        sheet = PackingMaterialsSheet.from_values(_values(message, attachment))
        return convert_packing_materials_to_order_format(sheet.items[0])

    def test_添付がある資材は発注成立後に送る(self) -> None:
        from order_packing_materials import send_material_attachments

        client = _SpyChatworkClient()
        results = [_Result([self._order("入稿データです", "https://drive.google.com/file/d/ABC/view")], "Y0806-1")]

        send_material_attachments(results, client)

        assert client.sent == [("入稿データです", "https://drive.google.com/file/d/ABC/view")]

    def test_注文が成立していなければ送らない(self) -> None:
        from order_packing_materials import send_material_attachments

        client = _SpyChatworkClient()
        results = [_Result([self._order("入稿データです", "https://drive.google.com/file/d/ABC/view")], None)]

        send_material_attachments(results, client)

        assert client.sent == []

    def test_添付が無い資材には何も送らない(self) -> None:
        from order_packing_materials import send_material_attachments

        client = _SpyChatworkClient()
        results = [_Result([self._order("", "")], "Y0806-1")]

        send_material_attachments(results, client)

        assert client.sent == []
