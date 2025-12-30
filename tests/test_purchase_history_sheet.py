from unittest.mock import Mock

from domain.value_objects.purchase_history import PurchaseHistoryItem, PurchaseHistorySheet


def test_add_history_returns_new_sheet_without_persist() -> None:
    sheet = PurchaseHistorySheet(items=[])
    item = PurchaseHistoryItem(
        purchase_date="2025-01-01",
        product_name="test",
        url="http://example.com",
        detail="",
        quantity=1,
        price=100.0,
        order_number="",
        material_name="",
    )

    new_sheet = sheet.add_history(item)

    assert len(sheet.items) == 0
    assert len(new_sheet.items) == 1
    assert new_sheet.items[0] == item


def test_add_history_and_persist_calls_repository_append() -> None:
    repo = Mock()
    sheet = PurchaseHistorySheet(items=[])
    item = PurchaseHistoryItem(
        purchase_date="2025-01-01",
        product_name="test",
        url="http://example.com",
        detail="",
        quantity=1,
        price=100.0,
        order_number="1234-00000000",
        material_name="資材A",
    )

    new_sheet = sheet.add_history(item=item, repository=repo)

    repo.append.assert_called_once_with(item)
    assert len(new_sheet.items) == 1

