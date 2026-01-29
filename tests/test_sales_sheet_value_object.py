import pandas as pd

from domain.value_objects.sales_sheet import SalesSheet


def test_sales_sheet_from_dataframe_skips_non_numeric_quantity():
    df = pd.DataFrame(
        {
            "ASIN": ["B001", "B002", "B003"],
            "発注数": ["10", "abc", 20],
            "商品名": ["p1", "p2", "p3"],
        }
    )

    sheet = SalesSheet.from_dataframe(df)

    assert len(sheet.items) == 2
    assert [i.asin for i in sheet.items] == ["B001", "B003"]
    assert [i.order_quantity for i in sheet.items] == [10, 20]



