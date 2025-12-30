from unittest.mock import Mock

import pandas as pd
import pytest

from domain.value_objects.purchase_info_sheet import PurchaseInfoSheet
from domain.value_objects.sales_sheet import SalesSheet
from domain.entities.order import Order
from usecases.exceptions import NoOrderDataException
from usecases.get_order_data_usecase import GetOrderDataUseCase


def test_get_order_data_usecase_execute_success():
    sales_df = pd.DataFrame(
        {
            "ASIN": ["B001", "B002", "B003"],
            "商品名": ["売上商品1", "売上商品2", "売上商品3"],
            "画像": ["img1", "img2", ""],
            "備考": ["memo1", "memo2", ""],
            "発注数": [10, 20, 15],
        }
    )
    purchase_df = pd.DataFrame(
        {
            "ASIN": ["B001", "B002"],
            "購入先URL": ["http://test1.com", "http://test2.com"],
            "題名": ["商品1", "商品2"],
            "色・サイズ等指定": ["Red/M", "Blue/L"],
            "1商品辺り発注数": [5, 10],
            "単価": [100, 200],
            "chatwork文章": ["", ""],
            "chatwork添付": ["", ""],
        }
    )

    mock_sales_repo = Mock()
    mock_sales_repo.read.return_value = SalesSheet.from_dataframe(sales_df)
    mock_purchase_repo = Mock()
    mock_purchase_repo.read.return_value = PurchaseInfoSheet.from_dataframe(purchase_df)

    usecase = GetOrderDataUseCase(
        sales_repository=mock_sales_repo,
        purchase_info_repository=mock_purchase_repo,
    )

    result = usecase.execute(sales_url="https://sales", purchase_url="https://purchase")

    assert len(result) == 2
    assert isinstance(result[0], Order)
    assert result[0].asin == "B001"
    assert result[0].order_quantity == 50
    assert result[0].sales_product_name == "売上商品1"
    assert result[0].image_text == "img1"
    assert result[0].remark_text == "memo1"
    assert result[1].asin == "B002"
    assert result[1].order_quantity == 200
    assert result[1].sales_product_name == "売上商品2"
    assert result[1].image_text == "img2"
    assert result[1].remark_text == "memo2"

    mock_sales_repo.read.assert_called_once()
    mock_purchase_repo.read.assert_called_once()


def test_get_order_data_usecase_execute_no_order_data_raises():
    sales_df = pd.DataFrame({"ASIN": ["B001"], "商品名": ["売上商品1"], "画像": ["img1"], "備考": ["memo1"], "発注数": [1]})
    purchase_df = pd.DataFrame(
        {
            "ASIN": ["B001"],
            "購入先URL": ["http://test.com"],
            "題名": ["商品1"],
            "色・サイズ等指定": [""],
            "1商品辺り発注数": [1],
            "単価": [100],
            "chatwork文章": [""],
            "chatwork添付": [""],
        }
    )

    mock_sales_repo = Mock()
    mock_sales_repo.read.return_value = SalesSheet.from_dataframe(sales_df)
    mock_purchase_repo = Mock()
    mock_purchase_repo.read.return_value = PurchaseInfoSheet.from_dataframe(purchase_df)

    usecase = GetOrderDataUseCase(
        sales_repository=mock_sales_repo,
        purchase_info_repository=mock_purchase_repo,
    )

    with pytest.raises(NoOrderDataException):
        usecase.execute(sales_url="https://sales", purchase_url="https://purchase")

