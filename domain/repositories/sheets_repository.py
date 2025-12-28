"""
Googleシートからデータを読み込むRepository
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from typing import Optional
from domain.value_objects.sales_sheet import SalesSheet
from domain.value_objects.purchase_info_sheet import PurchaseInfoSheet
from domain.value_objects.packing_materials_sheet import PackingMaterialsSheet
from domain.value_objects.purchase_history import PurchaseHistorySheet, PurchaseHistoryItem


class SheetsRepository:
    def __init__(self, credentials_file: str):
        self.credentials_file = credentials_file
        self.client = None
        self._authenticate()
    
    def _authenticate(self):
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            self.client = gspread.authorize(credentials)
            print("✓ Google Sheets APIの認証に成功しました")
        except Exception as e:
            raise Exception(f"Google Sheets APIの認証に失敗しました: {e}")
    
    def read_sales_sheet(self, sheet_url: str, sheet_name: str = "売上/日") -> SalesSheet:
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # 全データを取得
            data = worksheet.get_all_values()
            
            if len(data) < 3:
                raise Exception("シートにデータがありません（列名は2行目、データは3行目以降が必要です）")
            
            # DataFrameに変換（列名は2行目、データは3行目以降）
            df = pd.DataFrame(data[2:], columns=data[1])
            
            # 必要な列のみ抽出（A列=ASIN(0)、2列目=発注数(1)）
            if len(df.columns) < 2:
                raise Exception(f"シートの列数が不足しています。必要: 2列以上, 実際: {len(df.columns)}列")
            
            # ilocを使って位置ベースで列を選択
            df_filtered = df.iloc[:, [0, 1]].copy()
            df_filtered.columns = ['ASIN', '発注数']
            
            # 空行を削除
            df_filtered = df_filtered[df_filtered['ASIN'].str.strip() != '']
            
            # 発注数を数値に変換
            df_filtered['発注数'] = pd.to_numeric(df_filtered['発注数'], errors='coerce')
            
            # 欠損値を含む行を削除
            df_filtered = df_filtered.dropna()
            
            print(f"✓ 「{sheet_name}」シートから{len(df_filtered)}件のデータを読み込みました")
            
            return SalesSheet.from_dataframe(df_filtered)
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートの読み込みに失敗しました: {e}")
    
    def read_purchase_info_sheet(self, sheet_url: str, sheet_name: str = "仕入情報") -> PurchaseInfoSheet:
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # 全データを取得
            data = worksheet.get_all_values()
            
            if len(data) < 3:
                raise Exception("シートにデータがありません（列名は2行目、データは3行目以降が必要です）")
            
            # DataFrameに変換（列名は2行目、データは3行目以降）
            df = pd.DataFrame(data[2:], columns=data[1])
            
            # 必要な列のみ抽出
            # A列=ASIN(0), D列=購入先URL(3), E列=題名(4), F列=色・サイズ等指定(5), G列=1商品辺り発注数(6), L列=単価(11)
            # M列からZ列=数量割引情報(12-25)
            
            if len(df.columns) < 12:  # L列(11)にアクセスするには最低12列必要
                raise Exception(f"シートの列数が不足しています。必要: 12列以上, 実際: {len(df.columns)}列")
            
            # 基本情報の列を選択
            required_columns = [0, 3, 4, 5, 6, 11]
            df_filtered = df.iloc[:, required_columns].copy()
            df_filtered.columns = ['ASIN', '購入先URL', '題名', '色・サイズ等指定', '1商品辺り発注数', '単価']
            
            # Chatwork列を検索して追加（列名で検索）
            chatwork_message_col = None
            chatwork_attachment_col = None
            for idx, col_name in enumerate(df.columns):
                col_name_lower = str(col_name).lower()
                if 'chatwork' in col_name_lower and ('文章' in col_name or 'message' in col_name_lower):
                    chatwork_message_col = idx
                elif 'chatwork' in col_name_lower and ('添付' in col_name or 'attachment' in col_name_lower):
                    chatwork_attachment_col = idx
            
            if chatwork_message_col is not None:
                df_filtered['chatwork文章'] = df.iloc[:, chatwork_message_col].values
            else:
                df_filtered['chatwork文章'] = ''
            
            if chatwork_attachment_col is not None:
                df_filtered['chatwork添付'] = df.iloc[:, chatwork_attachment_col].values
            else:
                df_filtered['chatwork添付'] = ''
            
            # M列からZ列の数量割引情報を取得（列インデックス12-25）
            # 最大26列まで読み込む（Z列まで）
            if len(df.columns) >= 26:
                # M列からZ列（インデックス12-25）を取得し、元の列名を保持
                # Chatwork列と基本列は除外
                excluded_indices = set(required_columns)
                if chatwork_message_col is not None:
                    excluded_indices.add(chatwork_message_col)
                if chatwork_attachment_col is not None:
                    excluded_indices.add(chatwork_attachment_col)
                
                for col_idx in range(12, 26):
                    if col_idx in excluded_indices:
                        continue
                    original_col_name = df.columns[col_idx]
                    df_filtered[original_col_name] = df.iloc[:, col_idx].values
            
            # 空行を削除
            df_filtered = df_filtered[df_filtered['ASIN'].str.strip() != '']
            
            # 数値列を数値に変換
            df_filtered['1商品辺り発注数'] = pd.to_numeric(df_filtered['1商品辺り発注数'], errors='coerce')
            df_filtered['単価'] = pd.to_numeric(df_filtered['単価'], errors='coerce')
            
            # 数量割引列も数値に変換（M列からZ列）
            if len(df.columns) >= 26:
                for col_idx in range(12, 26):
                    original_col_name = df.columns[col_idx]
                    if original_col_name in df_filtered.columns:
                        df_filtered[original_col_name] = pd.to_numeric(df_filtered[original_col_name], errors='coerce')
            
            # 欠損値を含む行を削除（ASINと題名と購入先URLは必須）
            df_filtered = df_filtered.dropna(subset=['ASIN', '題名', '購入先URL'])
            
            print(f"✓ 「{sheet_name}」シートから{len(df_filtered)}件のデータを読み込みました")
            
            return PurchaseInfoSheet.from_dataframe(df_filtered)
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートの読み込みに失敗しました: {e}")
    
    def read_packing_materials_sheet(self, sheet_url: str, sheet_name: str = "使用資材") -> PackingMaterialsSheet:
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            packing_materials_sheet = PackingMaterialsSheet.from_sheet(worksheet)
            print(f"✓ 「{sheet_name}」シートから{len(packing_materials_sheet.items)}件のデータを読み込みました")
            return packing_materials_sheet
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートの読み込みに失敗しました: {e}")
    
    def read_purchase_history_sheet(self, sheet_url: str, sheet_name: str = "使用資材", start_row: int = 2) -> PurchaseHistorySheet:
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            data = worksheet.get_all_values()
            
            if len(data) < start_row + 1:
                raise Exception(f"シートにデータがありません（列名は{start_row}行目、データは{start_row + 1}行目以降が必要です）")
            
            df = pd.DataFrame(data[start_row:], columns=data[start_row - 1])
            
            if len(df.columns) < 29:  # AB列(28)にアクセスするには最低29列必要
                raise Exception(f"シートの列数が不足しています。必要: 29列以上, 実際: {len(df.columns)}列")
            
            df_filtered = df.iloc[:, 23:29].copy()
            df_filtered.columns = data[start_row - 1][23:29]
            
            column_mapping = {}
            for col_name in df_filtered.columns:
                col_name_str = str(col_name).strip()
                col_name_lower = col_name_str.lower()
                
                if not column_mapping.get('purchase_date') and ('購入日' in col_name_str or 'date' in col_name_lower or '日付' in col_name_str):
                    column_mapping['purchase_date'] = col_name
                elif not column_mapping.get('product_name') and ('商品名' in col_name_str or 'product' in col_name_lower or 'name' in col_name_lower):
                    column_mapping['product_name'] = col_name
                elif not column_mapping.get('url') and ('url' in col_name_lower or 'リンク' in col_name_str):
                    column_mapping['url'] = col_name
                elif not column_mapping.get('detail') and ('詳細' in col_name_str or 'detail' in col_name_lower or 'description' in col_name_lower or '備考' in col_name_str):
                    column_mapping['detail'] = col_name
                elif not column_mapping.get('quantity') and ('数量' in col_name_str or 'quantity' in col_name_lower or '発注数' in col_name_str):
                    column_mapping['quantity'] = col_name
                elif not column_mapping.get('price') and ('価格' in col_name_str or 'price' in col_name_lower or '単価' in col_name_str):
                    column_mapping['price'] = col_name
            
            purchase_date_col = column_mapping.get('purchase_date', '')
            product_name_col = column_mapping.get('product_name', '')
            url_col = column_mapping.get('url', '')
            detail_col = column_mapping.get('detail', '')
            quantity_col = column_mapping.get('quantity', '')
            price_col = column_mapping.get('price', '')
            
            if not product_name_col or not url_col:
                raise Exception("商品名とURLの列が見つかりません")
            
            print(f"✓ 「{sheet_name}」シートから購入履歴{len(df_filtered)}件を読み込みました")
            
            return PurchaseHistorySheet.from_dataframe(
                df_filtered,
                purchase_date_col,
                product_name_col,
                url_col,
                detail_col,
                quantity_col,
                price_col
            )
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートの購入履歴読み込みに失敗しました: {e}")
    
    def append_purchase_history(self, sheet_url: str, history_item: PurchaseHistoryItem, sheet_name: str = "使用資材") -> bool:
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            data = worksheet.get_all_values()
            if len(data) < 2:
                raise Exception("シートに列名がありません（2行目にヘッダーが必要です）")

            headers = data[1]

            start_col_idx = 25  # Z列 (0-index)
            end_col_idx_inclusive = 29  # AD列 (0-index)
            if len(headers) <= end_col_idx_inclusive:
                raise Exception(
                    f"シートの列数が不足しています。必要: {end_col_idx_inclusive + 1}列以上, 実際: {len(headers)}列"
                )

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
                "購入日": history_item.purchase_date,
                "注文日": history_item.purchase_date,
                "注文番号": history_item.order_number,
                "発注資材名称": history_item.material_name,
                "商品名": history_item.product_name,
                "URL": history_item.url,
                "詳細": history_item.detail,
                "数量": str(history_item.quantity),
                "発注数": str(history_item.quantity),
                "個数": str(history_item.quantity),
                "価格": str(history_item.price),
                "単価": str(history_item.price),
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

            print(f"✓ 「{sheet_name}」シートのZ{target_row}:AD{target_row}に購入履歴を記録しました: {history_item.product_name}")
            
            return True
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートへの購入履歴の追加に失敗しました: {e}")



