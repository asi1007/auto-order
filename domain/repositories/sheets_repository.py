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
            
            data = worksheet.get_all_values()
            
            if len(data) < 3:
                raise Exception("シートにデータがありません（列名は2行目、データは3行目以降が必要です）")
            
            df = pd.DataFrame(data[2:], columns=data[1])
            
            if len(df.columns) < 21:  # U列(20)にアクセスするには最低21列必要
                raise Exception(f"シートの列数が不足しています。必要: 21列以上, 実際: {len(df.columns)}列")
            
            df_filtered = df.iloc[:, 4:21].copy()
            df_filtered.columns = data[1][4:21]
            
            column_mapping = {}
            for col_name in df_filtered.columns:
                col_name_str = str(col_name).strip()
                col_name_lower = col_name_str.lower()
                
                if not column_mapping.get('url') and ('url' in col_name_lower or 'リンク' in col_name_str):
                    column_mapping['url'] = col_name
                elif not column_mapping.get('product_name') and ('商品名' in col_name_str or 'product' in col_name_lower or ('name' in col_name_lower and 'product' in col_name_lower)):
                    column_mapping['product_name'] = col_name
                elif not column_mapping.get('detail') and ('詳細' in col_name_str or 'detail' in col_name_lower or 'description' in col_name_lower or '備考' in col_name_str):
                    column_mapping['detail'] = col_name
                elif not column_mapping.get('price') and ('価格' in col_name_str or 'price' in col_name_lower or '単価' in col_name_str):
                    column_mapping['price'] = col_name
                elif not column_mapping.get('order_quantity') and ('発注数' in col_name_str or 'order' in col_name_lower or 'quantity' in col_name_lower or '数量' in col_name_str):
                    column_mapping['order_quantity'] = col_name
            
            if 'url' not in column_mapping or 'product_name' not in column_mapping:
                raise Exception(f"必要な列が見つかりません。見つかった列: {list(column_mapping.keys())}")
            
            url_col = column_mapping.get('url')
            product_name_col = column_mapping.get('product_name')
            detail_col = column_mapping.get('detail', '')
            price_col = column_mapping.get('price', '')
            order_quantity_col = column_mapping.get('order_quantity', '')
            
            if not url_col or not product_name_col:
                raise Exception("urlと商品名の列が見つかりません")
            
            print(f"✓ 「{sheet_name}」シートから{len(df_filtered)}件のデータを読み込みました")
            
            return PackingMaterialsSheet.from_dataframe(
                df_filtered,
                url_col,
                product_name_col,
                detail_col,
                price_col,
                order_quantity_col
            )
            
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
                raise Exception("シートに列名がありません")
            
            headers = data[1]
            
            if len(headers) < 29:
                raise Exception(f"シートの列数が不足しています。必要: 29列以上, 実際: {len(headers)}列")
            
            column_mapping = {}
            for idx, col_name in enumerate(headers[23:29], start=23):
                col_name_str = str(col_name).strip()
                col_name_lower = col_name_str.lower()
                
                if not column_mapping.get('purchase_date') and ('購入日' in col_name_str or 'date' in col_name_lower or '日付' in col_name_str):
                    column_mapping['purchase_date'] = idx
                elif not column_mapping.get('product_name') and ('商品名' in col_name_str or 'product' in col_name_lower or 'name' in col_name_lower):
                    column_mapping['product_name'] = idx
                elif not column_mapping.get('url') and ('url' in col_name_lower or 'リンク' in col_name_str):
                    column_mapping['url'] = idx
                elif not column_mapping.get('detail') and ('詳細' in col_name_str or 'detail' in col_name_lower or 'description' in col_name_lower or '備考' in col_name_str):
                    column_mapping['detail'] = idx
                elif not column_mapping.get('quantity') and ('数量' in col_name_str or 'quantity' in col_name_lower or '発注数' in col_name_str):
                    column_mapping['quantity'] = idx
                elif not column_mapping.get('price') and ('価格' in col_name_str or 'price' in col_name_lower or '単価' in col_name_str):
                    column_mapping['price'] = idx
            
            purchase_date_col = column_mapping.get('purchase_date')
            product_name_col = column_mapping.get('product_name')
            url_col = column_mapping.get('url')
            detail_col = column_mapping.get('detail')
            quantity_col = column_mapping.get('quantity')
            price_col = column_mapping.get('price')
            
            if product_name_col is None or url_col is None:
                raise Exception("商品名とURLの列が見つかりません")
            
            new_row = [''] * len(headers)
            
            if purchase_date_col is not None:
                new_row[purchase_date_col] = history_item.purchase_date
            if product_name_col is not None:
                new_row[product_name_col] = history_item.product_name
            if url_col is not None:
                new_row[url_col] = history_item.url
            if detail_col is not None:
                new_row[detail_col] = history_item.detail
            if quantity_col is not None:
                new_row[quantity_col] = str(history_item.quantity)
            if price_col is not None:
                new_row[price_col] = str(history_item.price)
            
            worksheet.append_row(new_row)
            
            print(f"✓ 「{sheet_name}」シートに購入履歴を追加しました: {history_item.product_name}")
            
            return True
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートへの購入履歴の追加に失敗しました: {e}")



