from unittest.mock import Mock

import pytest

from infrastructure.repositories.sales_sheet_repository import SheetsSalesSheetRepository


def test_sales_sheet_repository_read_success():
    mock_worksheet = Mock()
    mock_worksheet.get_all_values.return_value = [
        ["1行目（無視）"],
        ["ASIN", "発注数"],
        ["B001", "10"],
        ["B002", "20"],
        ["B003", "15"],
    ]

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsSalesSheetRepository("dummy_credentials.json", client=mock_client)
    sheet = repo.read("https://test.url")

    assert len(sheet.items) == 3
    assert sheet.items[0].asin == "B001"
    assert sheet.items[0].order_quantity == 10


def test_sales_sheet_repository_read_empty_data_raises():
    mock_worksheet = Mock()
    mock_worksheet.get_all_values.return_value = [
        ["1行目（無視）"],
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

