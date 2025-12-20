"""
Googleシートからデータを読み込むRepository
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from typing import Optional
from domain.value_objects.sales_sheet import SalesSheet
from domain.value_objects.purchase_info_sheet import PurchaseInfoSheet


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



