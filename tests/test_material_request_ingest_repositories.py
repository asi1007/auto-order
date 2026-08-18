from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

from infrastructure.processed_message_store import ProcessedMessageStore
from infrastructure.repositories.packing_materials_sheet_repository import (
    SheetsPackingMaterialsSheetRepository,
)
from infrastructure.repositories.purchase_history_sheet_repository import (
    SheetsPurchaseHistoryRepository,
)

_SHEET_URL = "https://test.url"


def _packing_worksheet() -> Mock:
    worksheet = Mock()
    worksheet.get_all_values.return_value = [
        ["1行目（無視）"] + [""] * 7,
        ["資材名称", "URL", "商品名", "詳細", "価格", "ロットサイズ", "発注数", "最終発注日"],
        ["OPP袋1", "https://example.com/1", "袋", "6*13(100个)*普通5丝", "10", "100", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["2L特注ダンボール", "https://example.com/3", "箱", "縦230 mm × 横183 mm", "30", "1", "", ""],
    ]
    return worksheet


class TestPackingMaterialsSheetRepositoryMaterialRows:
    def test_資材名称のない行を読み飛ばして行番号付きで返す(self) -> None:
        worksheet = _packing_worksheet()
        repo = SheetsPackingMaterialsSheetRepository("dummy.json", client=Mock())
        repo.open_worksheet = Mock(return_value=worksheet)

        rows = repo.read_material_rows(_SHEET_URL, sheet_name="使用資材")

        assert [(row.row_number, row.name) for row in rows] == [
            (3, "OPP袋1"),
            (5, "2L特注ダンボール"),
        ]
        assert rows[0].dimension_values == frozenset({6.0, 13.0, 5.0})

    def test_指定した行の発注数列だけを更新する(self) -> None:
        worksheet = _packing_worksheet()
        repo = SheetsPackingMaterialsSheetRepository("dummy.json", client=Mock())
        repo.open_worksheet = Mock(return_value=worksheet)

        repo.set_order_quantities(_SHEET_URL, {3: 30000, 5: 3000}, sheet_name="使用資材")

        calls = worksheet.update.call_args_list
        assert [call[0][0] for call in calls] == ["G3", "G5"]
        assert [call[0][1] for call in calls] == [[[30000]], [[3000]]]


class TestPurchaseHistoryRepositoryLatestQuantity:
    def test_同じ資材の最も新しい行の個数を返す(self) -> None:
        worksheet = Mock()
        headers = [""] * 25 + ["発注資材名称", "注文日", "注文番号", "個数", "残量"]
        worksheet.get_all_values.return_value = [
            [""] * 30,
            headers,
            [""] * 25 + ["A4プチプチ", "2026-05-01", "Y-1", "5000", ""],
            [""] * 25 + ["A4プチプチ", "2026-07-13", "Y-2", "10000", ""],
            [""] * 25 + ["OPP袋3", "2026-06-10", "", "30000", ""],
        ]
        repo = SheetsPurchaseHistoryRepository("dummy.json", _SHEET_URL, client=Mock())
        repo.open_worksheet = Mock(return_value=worksheet)

        quantities = repo.latest_quantity_by_material()

        assert quantities["A4プチプチ"] == 10000

    def test_注文番号のない未成立の発注は実績として扱わない(self) -> None:
        worksheet = Mock()
        headers = [""] * 25 + ["発注資材名称", "注文日", "注文番号", "個数", "残量"]
        worksheet.get_all_values.return_value = [
            [""] * 30,
            headers,
            [""] * 25 + ["OPP袋3", "2026-06-10", "", "30000", ""],
        ]
        repo = SheetsPurchaseHistoryRepository("dummy.json", _SHEET_URL, client=Mock())
        repo.open_worksheet = Mock(return_value=worksheet)

        assert "OPP袋3" not in repo.latest_quantity_by_material()


class TestProcessedMessageStore:
    def test_記録したメッセージだけを処理済みとして扱う(self, tmp_path: Path) -> None:
        store = ProcessedMessageStore(tmp_path / "state.json")

        store.mark_processed(["100", "200"])

        assert store.is_processed("100")
        assert not store.is_processed("300")

    def test_記録は別インスタンスからも読める(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        ProcessedMessageStore(path).mark_processed(["100"])

        assert ProcessedMessageStore(path).is_processed("100")

    def test_追記しても既存の記録を失わない(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        store = ProcessedMessageStore(path)
        store.mark_processed(["100"])
        store.mark_processed(["200"])

        assert json.loads(path.read_text())["processed_message_ids"] == ["100", "200"]

    def test_state_ファイルが無ければ未処理として扱う(self, tmp_path: Path) -> None:
        assert not ProcessedMessageStore(tmp_path / "missing.json").is_processed("100")
