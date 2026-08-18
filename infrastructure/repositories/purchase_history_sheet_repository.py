from __future__ import annotations

from infrastructure.repositories.base_sheets_repository import BaseSheetsRepository
from domain.value_objects.purchase_history import PurchaseHistoryItem


class SheetsPurchaseHistoryRepository(BaseSheetsRepository):
    def __init__(self, credentials_file: str, sheet_url: str, sheet_name: str = "使用資材", client=None):
        super().__init__(credentials_file=credentials_file, client=client)
        self.sheet_url = sheet_url
        self.sheet_name = sheet_name

    def latest_quantity_by_material(self) -> dict[str, int]:
        worksheet = self.open_worksheet(self.sheet_url, self.sheet_name)
        data = worksheet.get_all_values()
        if len(data) < 2:
            return {}

        headers = [str(h).strip() for h in data[1]]
        idx_name = headers.index("発注資材名称")
        idx_order_number = headers.index("注文番号")
        idx_quantity = headers.index("個数")

        # 注文日は「9/17」「2026-07-29」が混在していて日付順に並べられない。
        # ログは発注のたびに末尾へ追記されるため、行の並び順を新しさとして扱う。
        latest: dict[str, int] = {}
        for row in data[2:]:
            if len(row) <= max(idx_name, idx_order_number, idx_quantity):
                continue
            name = str(row[idx_name]).strip()
            order_number = str(row[idx_order_number]).strip()
            quantity = str(row[idx_quantity]).strip()
            if not name or not order_number or not quantity:
                continue
            latest[name] = int(float(quantity))
        return latest

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

