from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from domain.repositories.purchase_info_sheet_repository import PurchaseInfoSheetRepository
from domain.repositories.sales_sheet_repository import SalesSheetRepository
from domain.services.order_merge_service import OrderMergeService
from domain.entities.order import Order
from usecases.exceptions import NoOrderDataException


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GetOrderDataUseCase:
    sales_repository: SalesSheetRepository
    purchase_info_repository: PurchaseInfoSheetRepository
    merge_service: OrderMergeService = OrderMergeService()

    def execute(
        self,
        *,
        sales_url: str,
        purchase_url: str,
        sales_sheet_name: str = "売上/日",
        purchase_sheet_name: str = "仕入情報",
        selling_price_sheet_name: str = "納品状況",
    ) -> list[Order]:
        logger.info("[ステップ1] Googleシートから発注データを読み込んでいます...")

        sales_sheet = self.sales_repository.read(sales_url, sales_sheet_name)
        purchase_info_sheet = self.purchase_info_repository.read(purchase_url, purchase_sheet_name)

        order_list: list[Order] = self.merge_service.merge(sales_sheet, purchase_info_sheet)
        if not order_list:
            logger.info("処理する発注データがありません")
            raise NoOrderDataException("処理する発注データがありません")

        # 納品状況シートから販売価格を読み取り、Orderに付与
        selling_prices = self.purchase_info_repository.read_selling_prices(
            purchase_url, selling_price_sheet_name
        )
        if selling_prices:
            order_list = [
                replace(order, selling_price=selling_prices[order.asin])
                if order.asin in selling_prices
                else order
                for order in order_list
            ]

        return order_list

