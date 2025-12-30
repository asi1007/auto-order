from __future__ import annotations

from domain.entities.order import Order

from infrastructure.repositories import BaseSheetsRepository, SheetsPurchaseInfoSheetRepository, SheetsSalesSheetRepository
from usecases.get_order_data_usecase import GetOrderDataUseCase
from usecases.exceptions import NoOrderDataException
from usecases.group_orders_by_url import group_orders_by_url


def get_order_data(credentials_file: str, sales_url: str, purchase_url: str) -> list[Order]:
    base = BaseSheetsRepository(credentials_file)
    usecase = GetOrderDataUseCase(
        sales_repository=SheetsSalesSheetRepository(credentials_file, client=base.client),
        purchase_info_repository=SheetsPurchaseInfoSheetRepository(credentials_file, client=base.client),
    )
    return usecase.execute(sales_url=sales_url, purchase_url=purchase_url)

