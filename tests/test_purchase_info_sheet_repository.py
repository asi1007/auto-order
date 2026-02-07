from unittest.mock import Mock

import pytest

from infrastructure.repositories.purchase_info_sheet_repository import SheetsPurchaseInfoSheetRepository


def test_purchase_info_sheet_repository_read_success():
    mock_worksheet = Mock()
    mock_worksheet.get_all_values.return_value = [
        ["1行目（無視）"],
        [
            "ASIN",
            "Col2",
            "Col3",
            "購入先URL",
            "題名",
            "色・サイズ等指定",
            "1商品辺り発注数",
            "Col8",
            "Col9",
            "Col10",
            "Col11",
            "単価",
        ],
        ["B001", "", "", "http://test1.com", "商品1", "Red/M", "5", "", "", "", "", "100"],
        ["B002", "", "", "http://test2.com", "商品2", "Blue/L", "10", "", "", "", "", "200"],
    ]

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseInfoSheetRepository("dummy_credentials.json", client=mock_client)
    sheet = repo.read("https://test.url")

    assert len(sheet.items) == 2
    assert sheet.items[0].asin == "B001"
    assert sheet.items[0].title == "商品1"
    assert sheet.items[0].quantity_per_item == 5


def test_purchase_info_sheet_repository_read_selling_prices():
    """納品状況シートからASIN→販売価格の辞書を正しく読み取る"""
    mock_worksheet = Mock()
    mock_worksheet.get_all_values.return_value = [
        ["ASIN", "商品名", "販売価格", "在庫数"],
        ["B001", "商品1", "1980", "50"],
        ["B002", "商品2", "2500", "30"],
        ["B003", "商品3", "", "10"],   # 販売価格が空
        ["", "商品4", "1000", "20"],   # ASINが空
    ]

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseInfoSheetRepository("dummy_credentials.json", client=mock_client)
    result = repo.read_selling_prices("https://test.url", "納品状況")

    assert result == {"B001": 1980.0, "B002": 2500.0}
    # B003（価格空）とASIN空の行はスキップされる


def test_purchase_info_sheet_repository_read_selling_prices_empty_sheet():
    """納品状況シートが空の場合は空辞書を返す"""
    mock_worksheet = Mock()
    mock_worksheet.get_all_values.return_value = []

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseInfoSheetRepository("dummy_credentials.json", client=mock_client)
    result = repo.read_selling_prices("https://test.url", "納品状況")

    assert result == {}


def test_purchase_info_sheet_repository_read_empty_data_raises():
    mock_worksheet = Mock()
    mock_worksheet.get_all_values.return_value = [
        ["1行目（無視）"],
        ["ASIN", "Col2", "Col3", "購入先URL", "題名", "色・サイズ等指定", "1商品辺り発注数", "Col8", "Col9", "Col10", "Col11", "単価"],
    ]

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseInfoSheetRepository("dummy_credentials.json", client=mock_client)

    with pytest.raises(Exception) as exc_info:
        repo.read("https://test.url")

    assert "シートにデータがありません" in str(exc_info.value)

