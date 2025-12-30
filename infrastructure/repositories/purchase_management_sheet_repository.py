from __future__ import annotations

import re
from typing import Any

from domain.value_objects.purchase_management import PurchaseManagementItem
from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository


def _extract_gid(sheet_url: str) -> int:
    match = re.search(r"[?&#]gid=(\d+)", sheet_url)
    if not match:
        raise ValueError("sheet_urlにgidがありません（例: ...?gid=123#gid=123）")
    return int(match.group(1))


class SheetsPurchaseManagementRepository(BaseSheetsRepository):
    """
    仕入管理シートへ追記するRepository。

    - worksheetはURLのgidで特定
    - ヘッダーは4行目
    - 4行目の列名を見てマッピングして追記
    """

    HEADER_ROW = 4

    def __init__(self, credentials_file: str, sheet_url: str, sheet_name: str | None = None, client=None):
        super().__init__(credentials_file=credentials_file, client=client)
        self.sheet_url = sheet_url
        self.sheet_name = sheet_name

    def append(self, item: PurchaseManagementItem) -> None:
        spreadsheet = self.client.open_by_url(self.sheet_url)
        worksheet = spreadsheet.worksheet(self.sheet_name)
        headers = worksheet.row_values(self.HEADER_ROW)
        if not headers:
            raise Exception("シートにヘッダーがありません（4行目にヘッダーが必要です）")

        value_by_header: dict[str, Any] = {
            "購入日": item.purchase_date,
            "注文日": item.purchase_date,
            "日付": item.purchase_date,
            "注文番号": item.order_number,
            "発注番号": item.order_number,
            "ASIN": item.asin,
            "商品名": item.product_name,
            # URLは「購入先」列にのみ入れる
            "購入先": item.url,
            "購入先URL": item.url,
            "画像": item.image_text,
            "備考": item.remark_text,
            "詳細": item.detail,
            "色": item.detail,
            "サイズ": item.detail,
            "数量": str(item.quantity),
            "発注数": str(item.quantity),
            "個数": str(item.quantity),
            "単価": "" if item.unit_price is None else str(item.unit_price),
            "価格": "" if item.unit_price is None else str(item.unit_price),
            "金額": "" if item.total_price is None else str(item.total_price),
            "合計": "" if item.total_price is None else str(item.total_price),
            "資材": item.material_name,
            "資材名称": item.material_name,
        }

        header_cells = [str(h).strip() for h in headers]
        row_values: list[Any] = []
        for header_name in header_cells:
            matched: Any = ""
            for key, value in value_by_header.items():
                if key and key in header_name:
                    matched = value
                    break
            row_values.append(matched)

        worksheet.append_row(row_values, value_input_option="USER_ENTERED")


