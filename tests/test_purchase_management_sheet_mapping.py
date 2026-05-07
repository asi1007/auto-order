from unittest.mock import Mock

from domain.value_objects.purchase_management import PurchaseManagementItem
from infrastructure.repositories.purchase_management_sheet_repository import SheetsPurchaseManagementRepository


def test_purchase_management_sheet_repository_writes_selling_price_to_cart_price_column():
    """selling_priceが「カート価格」列に書き込まれる"""
    mock_worksheet = Mock()
    mock_worksheet.row_values.return_value = ["ASIN", "商品名", "カート価格", "購入数"]
    mock_worksheet.row_count = 100
    mock_worksheet.id = 123
    mock_worksheet.get.side_effect = [
        [["x"]],  # key column scan
        [["", "", "", ""]],  # prev row formulas (none)
    ]
    mock_worksheet.update = Mock()
    mock_worksheet.add_rows = Mock()

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    mock_spreadsheet.fetch_sheet_metadata.return_value = {"sheets": []}
    mock_spreadsheet.batch_update = Mock()

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseManagementRepository(
        "dummy.json",
        "https://example.com/sheet",
        sheet_name="仕入管理",
        client=mock_client,
    )

    item = PurchaseManagementItem(
        purchase_date="2025-01-01",
        order_number="2025-12345678",
        asin="A1",
        product_name="売上商品",
        url="",
        detail="",
        quantity=3,
        image_text="",
        remark_text="",
        delivery_category="",
        selling_price=1980.0,
        unit_price=None,
        total_price=None,
        material_name="",
    )

    repo.append(item)

    update_values = mock_worksheet.update.call_args[0][1]
    # カート価格列(3列目)に1980が入る
    assert update_values[0][2] == 1980


def test_purchase_management_sheet_repository_writes_purchase_count_currency_and_purchase_url():
    mock_worksheet = Mock()
    mock_worksheet.row_values.return_value = ["購入先", "購入数", "通貨", "商品名", "納品分類"]
    mock_worksheet.row_count = 100
    mock_worksheet.id = 123
    # A5:A100 -> 最終入力行=6, 追記行=7 となる想定
    mock_worksheet.get.side_effect = [
        [["x"], ["y"]],  # key column scan
        [["", "", "", "", ""]],  # prev row formulas (none)
    ]
    mock_worksheet.update = Mock()
    mock_worksheet.add_rows = Mock()

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    mock_spreadsheet.fetch_sheet_metadata.return_value = {"sheets": []}
    mock_spreadsheet.batch_update = Mock()

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseManagementRepository(
        "dummy.json",
        "https://example.com/sheet",
        sheet_name="仕入管理",
        client=mock_client,
    )

    item = PurchaseManagementItem(
        purchase_date="2025-01-01",
        order_number="2025-12345678",
        asin="A1",
        product_name="売上商品",
        url="https://buy.example.com/item",
        detail="",
        quantity=3,
        image_text="",
        remark_text="",
        delivery_category="特別",
        unit_price=None,
        total_price=None,
        material_name="",
    )

    repo.append(item)

    # header順に値が埋まっていること（追記行=7）
    mock_worksheet.update.assert_called_once()
    update_range = mock_worksheet.update.call_args[0][0]
    update_values = mock_worksheet.update.call_args[0][1]
    assert update_range == "A7:E7"
    assert update_values == [["https://buy.example.com/item", 3, "CNY", "売上商品", "特別"]]
    mock_spreadsheet.batch_update.assert_not_called()


def test_purchase_management_sheet_repository_copies_formulas_from_previous_row_when_empty():
    mock_worksheet = Mock()
    mock_worksheet.row_values.return_value = ["購入先", "金額", "通貨", "合計", "商品名"]
    mock_worksheet.row_count = 100
    mock_worksheet.id = 123
    # A5:A100 -> 最終入力行=6, 追記行=7
    # A6:E6 -> 2列目/4列目が数式
    mock_worksheet.get.side_effect = [
        [["x"], ["y"]],
        [["", "=B6*2", "", "=SUM(B6:B6)", ""]],
    ]
    mock_worksheet.update = Mock()
    mock_worksheet.add_rows = Mock()

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    mock_spreadsheet.fetch_sheet_metadata.return_value = {"sheets": []}
    mock_spreadsheet.batch_update = Mock()

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseManagementRepository(
        "dummy.json",
        "https://example.com/sheet",
        sheet_name="仕入管理",
        client=mock_client,
    )

    item = PurchaseManagementItem(
        purchase_date="2025-01-01",
        order_number="2025-12345678",
        asin="A1",
        product_name="売上商品",
        url="https://buy.example.com/item",
        detail="",
        quantity=3,
        image_text="",
        remark_text="",
        delivery_category="",
        unit_price=None,
        total_price=None,
        material_name="",
    )

    repo.append(item)

    # 値の更新はされる
    mock_worksheet.update.assert_called_once()

    # 数式コピーの copyPaste が発行される（2列目と4列目）
    mock_spreadsheet.batch_update.assert_called_once()
    body = mock_spreadsheet.batch_update.call_args[0][0]
    requests = body["requests"]
    assert any("copyPaste" in r for r in requests)
    copy_pastes = [r["copyPaste"] for r in requests if "copyPaste" in r]
    assert len(copy_pastes) == 2
    # 2列目（0-based 1）と4列目（0-based 3）の2箇所がコピーされる
    col_ranges = {(cp["source"]["startColumnIndex"], cp["source"]["endColumnIndex"]) for cp in copy_pastes}
    assert col_ranges == {(1, 2), (3, 4)}
    for cp in copy_pastes:
        assert cp["source"]["startRowIndex"] == 5  # prev_row=6
        assert cp["destination"]["startRowIndex"] == 6  # target_row=7


def test_purchase_management_sheet_repository_does_not_copy_formula_for_plan_alias():
    """プラン別名 列は前行が数式でも空白のまま（数式コピー対象外）"""
    mock_worksheet = Mock()
    mock_worksheet.row_values.return_value = ["ASIN", "商品名", "プラン別名", "購入数"]
    mock_worksheet.row_count = 100
    mock_worksheet.id = 123
    mock_worksheet.get.side_effect = [
        [["x"], ["y"]],  # key column scan -> target_row=7
        [["", "", '=VLOOKUP(D6,$Z:$AA,2,FALSE)', ""]],  # 前行: プラン別名が数式
    ]
    mock_worksheet.update = Mock()
    mock_worksheet.add_rows = Mock()

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    mock_spreadsheet.fetch_sheet_metadata.return_value = {"sheets": []}
    mock_spreadsheet.batch_update = Mock()

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseManagementRepository(
        "dummy.json",
        "https://example.com/sheet",
        sheet_name="仕入管理",
        client=mock_client,
    )

    item = PurchaseManagementItem(
        purchase_date="2025-01-01",
        order_number="2025-12345678",
        asin="A1",
        product_name="売上商品",
        url="",
        detail="",
        quantity=3,
        image_text="",
        remark_text="",
        delivery_category="",
        unit_price=None,
        total_price=None,
        material_name="",
    )

    repo.append(item)

    # プラン別名 列(0-based 2)は数式コピーリクエストに含まれないこと
    if mock_spreadsheet.batch_update.called:
        body = mock_spreadsheet.batch_update.call_args[0][0]
        copy_pastes = [r["copyPaste"] for r in body["requests"] if "copyPaste" in r]
        for cp in copy_pastes:
            assert not (cp["source"]["startColumnIndex"] <= 2 < cp["source"]["endColumnIndex"]), (
                f"プラン別名 列(idx=2)は数式コピー対象外であること: {cp}"
            )


def test_purchase_management_sheet_repository_expands_basic_filter_range_to_new_row():
    mock_worksheet = Mock()
    mock_worksheet.row_values.return_value = ["購入先", "購入数", "通貨", "商品名", "納品分類"]
    mock_worksheet.row_count = 100
    mock_worksheet.id = 123
    mock_worksheet.get.side_effect = [
        [["x"], ["y"]],  # key column scan -> target_row=7
        [["", "", "", "", ""]],  # prev row formulas (none)
    ]
    mock_worksheet.update = Mock()
    mock_worksheet.add_rows = Mock()

    mock_spreadsheet = Mock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    mock_spreadsheet.fetch_sheet_metadata.return_value = {
        "sheets": [
            {
                "properties": {"sheetId": 123, "title": "仕入管理"},
                "basicFilter": {
                    "range": {
                        "sheetId": 123,
                        "startRowIndex": 3,
                        "endRowIndex": 6,  # row6まで。row7を含むように拡張される想定
                        "startColumnIndex": 0,
                        "endColumnIndex": 5,
                    },
                    "criteria": {},
                },
            }
        ]
    }
    mock_spreadsheet.batch_update = Mock()

    mock_client = Mock()
    mock_client.open_by_url.return_value = mock_spreadsheet

    repo = SheetsPurchaseManagementRepository(
        "dummy.json",
        "https://example.com/sheet",
        sheet_name="仕入管理",
        client=mock_client,
    )

    item = PurchaseManagementItem(
        purchase_date="2025-01-01",
        order_number="2025-12345678",
        asin="A1",
        product_name="売上商品",
        url="https://buy.example.com/item",
        detail="",
        quantity=3,
        image_text="",
        remark_text="",
        delivery_category="",
        unit_price=None,
        total_price=None,
        material_name="",
    )

    repo.append(item)

    mock_spreadsheet.batch_update.assert_called_once()
    body = mock_spreadsheet.batch_update.call_args[0][0]
    requests = body["requests"]
    set_basic = [r["setBasicFilter"]["filter"] for r in requests if "setBasicFilter" in r]
    assert len(set_basic) == 1
    # endRowIndexは0-based exclusiveなので、row 7(1-based)を含めるには8が必要
    assert set_basic[0]["range"]["endRowIndex"] == 8



