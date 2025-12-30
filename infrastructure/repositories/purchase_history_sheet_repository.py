from __future__ import annotations

from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository
from domain.value_objects.purchase_history import PurchaseHistoryItem


class SheetsPurchaseHistoryRepository(BaseSheetsRepository):
    def __init__(self, credentials_file: str, sheet_url: str, sheet_name: str = "使用資材", client=None):
        super().__init__(credentials_file=credentials_file, client=client)
        self.sheet_url = sheet_url
        self.sheet_name = sheet_name

    def append(self, item: PurchaseHistoryItem) -> None:
        worksheet = self.open_worksheet(self.sheet_url, self.sheet_name)
        data = worksheet.get_all_values()
        if len(data) < 2:
            raise Exception("シートに列名がありません（2行目にヘッダーが必要です）")

        headers = data[1]

        start_col_idx = 25  # Z列 (0-index)
        end_col_idx_inclusive = 29  # AD列 (0-index)
        if len(headers) <= end_col_idx_inclusive:
            raise Exception(f"シートの列数が不足しています。必要: {end_col_idx_inclusive + 1}列以上, 実際: {len(headers)}列")

        header_slice = [str(h).strip() for h in headers[start_col_idx : end_col_idx_inclusive + 1]]

        start_row = 3
        range_values = worksheet.get(f"Z{start_row}:AD{worksheet.row_count}")

        last_filled_offset = -1
        for idx, row in enumerate(range_values):
            if any(str(cell).strip() for cell in row):
                last_filled_offset = idx

        target_row = start_row + last_filled_offset + 1
        if target_row > worksheet.row_count:
            worksheet.add_rows(target_row - worksheet.row_count)

        value_by_header = {
            "購入日": item.purchase_date,
            "注文日": item.purchase_date,
            "注文番号": item.order_number,
            "発注資材名称": item.material_name,
            "商品名": item.product_name,
            "URL": item.url,
            "詳細": item.detail,
            "数量": str(item.quantity),
            "発注数": str(item.quantity),
            "個数": str(item.quantity),
            "価格": str(item.price),
            "単価": str(item.price),
        }

        row_values = []
        for header_name in header_slice:
            matched = ""
            for key, value in value_by_header.items():
                if key and key in header_name:
                    matched = value
                    break
            row_values.append(matched)

        worksheet.update(f"Z{target_row}:AD{target_row}", [row_values])

