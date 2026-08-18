from __future__ import annotations

from domain.services.material_request_parser import MaterialRequestParser


class TestMaterialRequestParser:
    def setup_method(self) -> None:
        self.parser = MaterialRequestParser()

    def test_単一サイズの在庫不足依頼を取り込む(self) -> None:
        request = self.parser.parse(
            message_id="2126625458237079552",
            sent_at=1783500620,
            body="[To:5437457]和田　篤さん\n230*183*20mm ケースが在庫不足ので、再注文してお願いいたします。",
        )

        assert request is not None
        assert request.message_id == "2126625458237079552"
        assert [token.text for token in request.size_tokens] == ["230*183*20mm"]
        assert request.size_tokens[0].values == frozenset({230.0, 183.0, 20.0})
        assert "ダンボール" in request.categories

    def test_複数サイズの依頼を全て取り込む(self) -> None:
        request = self.parser.parse(
            message_id="2134227481438588928",
            sent_at=1785297203,
            body=(
                "[To:2802562]古茶大輝さん\n在庫不足の分、再注文してお願いいたします。\n"
                "ケース260*203*20mm \nケース310*226*23MM\nケース348*260*20mm"
            ),
        )

        assert request is not None
        assert [token.text for token in request.size_tokens] == [
            "260*203*20mm",
            "310*226*23MM",
            "348*260*20mm",
        ]

    def test_サイズ表記がなくても依頼として取り込む(self) -> None:
        request = self.parser.parse(
            message_id="2138859235856228352",
            sent_at=1786755720,
            body="[To:5437457]和田　篤さん\nこの商品用の袋が足りなくて、再注文してお願いいたします。",
        )

        assert request is not None
        assert request.size_tokens == ()
        assert "袋" in request.categories

    def test_納品書の依頼は梱包サイズが書かれていても取り込まない(self) -> None:
        request = self.parser.parse(
            message_id="2128792322975346688",
            sent_at=1784017200,
            body=(
                "[To:2802562]古茶大輝さん\nこの分は作業しました。\n"
                "1件を梱包しました。\n30*40*50ｃｍです。26.5KGです。\n納品書をお願いいたします。"
            ),
        )

        assert request is None

    def test_資材以外の不足連絡は取り込まない(self) -> None:
        request = self.parser.parse(
            message_id="2131948305541107712",
            sent_at=1785115260,
            body="税金の口座金額が足りなくて、\n入金をご手配してお願い致します。",
        )

        assert request is None

    def test_引用部分の記述は判定に使わない(self) -> None:
        request = self.parser.parse(
            message_id="2128263396922363904",
            sent_at=1784063880,
            body=(
                "[qt][qtmeta aid=986396 time=1783566495]30*35のプチプチ袋が在庫なくて、"
                "再注文してお願いいたします。[/qt]お願いします。発注は完了しました。"
            ),
        )

        assert request is None

    def test_全角のサイズ表記を半角に正規化する(self) -> None:
        request = self.parser.parse(
            message_id="1",
            sent_at=0,
            body="ＯＰＰ袋が在庫不足なので再注文してください。６＊１３です。",
        )

        assert request is not None
        assert request.size_tokens[0].values == frozenset({6.0, 13.0})
        assert "OPP" in request.categories

    def test_サイズ表記に含まれる数値がひとつだけなら採用しない(self) -> None:
        request = self.parser.parse(
            message_id="1",
            sent_at=0,
            body="ケースが在庫不足ので、再注文してお願いいたします。20個です。",
        )

        assert request is not None
        assert request.size_tokens == ()
