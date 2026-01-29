from unittest.mock import Mock

import pytest

from infrastructure.repositories.sales_sheet_repository import SheetsSalesSheetRepository


def test_sales_sheet_repository_read_success():
    mock_worksheet = Mock()
    # 画像列はFORMULAで取得される想定
    mock_worksheet.get_all_values.return_value = [
        ["1行目（無視）"],
        ["2行目（無視）"],
        ["ASIN", "商品名", "画像", "備考", "納品分類", "発注数"],
        ["B001", "売上の商品1", '=IMAGE("https://example.com/1.png")', "memo1", "特別", "10"],
        ["B002", "売上の商品2", "img2", "memo2", "通常", "20"],
        ["B003", "売上の商品3", "", "", "", "15"],
    ]

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsSalesSheetRepository("dummy_credentials.json", client=mock_client)
    sheet = repo.read("https://test.url")

    mock_worksheet.get_all_values.assert_called_once_with(value_render_option="FORMULA")
    assert len(sheet.items) == 3
    assert sheet.items[0].asin == "B001"
    assert sheet.items[0].order_quantity == 10
    assert sheet.items[0].product_name == "売上の商品1"
    assert sheet.items[0].image_text == '=IMAGE("https://example.com/1.png")'
    assert sheet.items[0].remark_text == "memo1"
    assert sheet.items[0].delivery_category == "特別"


def test_sales_sheet_repository_read_empty_data_raises():
    mock_worksheet = Mock()
    mock_worksheet.get_all_values.return_value = [
        ["1行目（無視）"],
        ["2行目（無視）"],
        ["ASIN", "発注数"],
    ]

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsSalesSheetRepository("dummy_credentials.json", client=mock_client)

    with pytest.raises(Exception) as exc_info:
        repo.read("https://test.url")

    assert "シートにデータがありません" in str(exc_info.value)


def test_sales_sheet_repository_clear_order_quantities_clears_only_target_asins():
    mock_worksheet = Mock()
    mock_worksheet.get_all_values.return_value = [
        ["1行目（無視）"],
        ["2行目（無視）"],
        # 実運用のシートは「発注数=2列目（B列）」想定
        ["ASIN", "発注数", "商品名"],
        ["B001", "10", "売上の商品1"],
        ["B002", "20", "売上の商品2"],
        ["B003", "15", "売上の商品3"],
    ]
    mock_worksheet.update = Mock()

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsSalesSheetRepository("dummy_credentials.json", client=mock_client)

    cleared = repo.clear_order_quantities("https://test.url", ["B001", "B003"])
    assert cleared == 2

    # 発注数列は2列目なので B列。B001は4行目、B003は6行目。
    calls = mock_worksheet.update.call_args_list
    assert len(calls) == 2
    assert calls[0][0][0] == "B4:B4"
    assert calls[0][0][1] == [[""]]
    assert calls[1][0][0] == "B6:B6"
    assert calls[1][0][1] == [[""]]

