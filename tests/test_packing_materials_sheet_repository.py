from unittest.mock import Mock

from infrastructure.repositories.packing_materials_sheet_repository import SheetsPackingMaterialsSheetRepository


def test_packing_materials_sheet_repository_clear_order_quantities_clears_only_target_materials():
    mock_worksheet = Mock()
    # 2行目がヘッダー、3行目以降がデータ想定
    mock_worksheet.get_all_values.return_value = [
        ["1行目（無視）"],
        ["資材名称", "発注数", "ロットサイズ", "URL", "商品名", "詳細", "価格"],
        ["OPP袋", "2", "1", "https://example.com/1", "袋", "", "10"],
        ["テープ", "0", "1", "https://example.com/2", "テープ", "", "20"],
        ["段ボール", "5", "1", "https://example.com/3", "箱", "", "30"],
    ]
    mock_worksheet.update = Mock()

    repo = SheetsPackingMaterialsSheetRepository("dummy.json", client=Mock())
    repo.open_worksheet = Mock(return_value=mock_worksheet)

    cleared = repo.clear_order_quantities("https://test.url", ["OPP袋", "段ボール"], sheet_name="使用資材")
    assert cleared == 2

    calls = mock_worksheet.update.call_args_list
    assert len(calls) == 2
    # 発注数は2列目（B列）。OPP袋は3行目、段ボールは5行目。
    assert calls[0][0][0] == "B3:B3"
    assert calls[0][0][1] == [[""]]
    assert calls[1][0][0] == "B5:B5"
    assert calls[1][0][1] == [[""]]

