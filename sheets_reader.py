"""
Googleシートから発注情報を読み込むモジュール
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from typing import List, Dict
import os


class SheetsReader:
    """Googleシートから発注情報を読み込むクラス"""
    
    def __init__(self, credentials_file: str):
        """
        初期化
        
        Args:
            credentials_file: Google Sheets API認証情報ファイルのパス
        """
        self.credentials_file = credentials_file
        self.client = None
        self._authenticate()
    
    def _authenticate(self):
        """Google Sheets APIの認証"""
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
    
    def read_sales_sheet(self, sheet_url: str, sheet_name: str = "売上/日") -> pd.DataFrame:
        """
        「売上/日」シートから発注数情報を読み込む
        
        Args:
            sheet_url: シートのURL
            sheet_name: シート名
            
        Returns:
            DataFrame: ASIN, 発注数の情報
        """
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # 全データを取得
            data = worksheet.get_all_values()
            
            if len(data) < 2:
                raise Exception("シートにデータがありません")
            
            # DataFrameに変換
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # 必要な列のみ抽出（A列=ASIN(0)、2列目=発注数(1)）
            # 列インデックスが存在するか確認
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
            
            return df_filtered
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートの読み込みに失敗しました: {e}")
    
    def read_purchase_sheet(self, sheet_url: str, sheet_name: str = "仕入情報") -> pd.DataFrame:
        """
        「仕入情報」シートから発注先情報を読み込む
        
        Args:
            sheet_url: シートのURL
            sheet_name: シート名
            
        Returns:
            DataFrame: ASIN, 題名, 購入先URL, 色・サイズ等指定, 1商品辺り発注数, 単価の情報
        """
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # 全データを取得
            data = worksheet.get_all_values()
            
            if len(data) < 2:
                raise Exception("シートにデータがありません")
            
            # DataFrameに変換
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # 必要な列のみ抽出
            # A列=ASIN(0), D列=購入先URL(3), E列=題名(4), F列=色・サイズ等指定(5), G列=1商品辺り発注数(6), L列=単価(11)
            
            # 列インデックスが存在するか確認
            required_columns = [0, 3, 4, 5, 6, 11]
            if len(df.columns) < 12:  # L列(11)にアクセスするには最低12列必要
                raise Exception(f"シートの列数が不足しています。必要: 12列以上, 実際: {len(df.columns)}列")
            
            # ilocを使って位置ベースで列を選択
            df_filtered = df.iloc[:, required_columns].copy()
            df_filtered.columns = ['ASIN', '購入先URL', '題名', '色・サイズ等指定', '1商品辺り発注数', '単価']
            
            # 空行を削除
            df_filtered = df_filtered[df_filtered['ASIN'].str.strip() != '']
            
            # 数値列を数値に変換
            df_filtered['1商品辺り発注数'] = pd.to_numeric(df_filtered['1商品辺り発注数'], errors='coerce')
            df_filtered['単価'] = pd.to_numeric(df_filtered['単価'], errors='coerce')
            
            # 欠損値を含む行を削除（ASINと題名と購入先URLは必須）
            df_filtered = df_filtered.dropna(subset=['ASIN', '題名', '購入先URL'])
            
            print(f"✓ 「{sheet_name}」シートから{len(df_filtered)}件のデータを読み込みました")
            
            return df_filtered
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートの読み込みに失敗しました: {e}")
    
    def merge_data(self, sales_df: pd.DataFrame, purchase_df: pd.DataFrame) -> List[Dict]:
        """
        売上/日シートと仕入情報シートのデータをASINで紐付けて発注数を計算
        
        Args:
            sales_df: 売上/日のDataFrame
            purchase_df: 仕入情報のDataFrame
            
        Returns:
            List[Dict]: 発注に必要な情報のリスト
        """
        # ASINでマージ
        merged_df = pd.merge(sales_df, purchase_df, on='ASIN', how='inner')
        
        if len(merged_df) == 0:
            print("警告: ASINで紐付けできるデータがありません")
            return []
        
        # 発注数を計算: 売上/日の発注数 × 仕入情報の1商品辺り発注数
        merged_df['最終発注数'] = merged_df['発注数'] * merged_df['1商品辺り発注数']
        
        # 整数に変換
        merged_df['最終発注数'] = merged_df['最終発注数'].astype(int)
        
        # 辞書のリストに変換
        order_list = []
        for _, row in merged_df.iterrows():
            order_info = {
                'ASIN': row['ASIN'],
                '商品名': row['題名'],
                '購入先URL': row['購入先URL'],
                '色・サイズ等指定': row['色・サイズ等指定'] if pd.notna(row['色・サイズ等指定']) else '',
                '発注数': int(row['最終発注数']),
                '単価': row['単価'] if pd.notna(row['単価']) else ''
            }
            order_list.append(order_info)
        
        print(f"✓ {len(order_list)}件の発注データを作成しました")
        
        # 紐付けできなかったASINを表示
        sales_asins = set(sales_df['ASIN'])
        purchase_asins = set(purchase_df['ASIN'])
        merged_asins = set(merged_df['ASIN'])
        
        unmatched_sales = sales_asins - merged_asins
        if unmatched_sales:
            print(f"警告: 以下のASINは仕入情報シートに存在しません: {unmatched_sales}")
        
        unmatched_purchase = purchase_asins - merged_asins
        if unmatched_purchase:
            print(f"情報: 以下のASINは売上/日シートに存在しません: {unmatched_purchase}")
        
        return order_list


def get_order_data(credentials_file: str, sales_url: str, purchase_url: str) -> List[Dict]:
    """
    Googleシートから発注データを取得する便利関数
    
    Args:
        credentials_file: Google Sheets API認証情報ファイルのパス
        sales_url: 売上/日シートのURL
        purchase_url: 仕入情報シートのURL
        
    Returns:
        List[Dict]: 発注に必要な情報のリスト
    """
    reader = SheetsReader(credentials_file)
    
    sales_df = reader.read_sales_sheet(sales_url)
    purchase_df = reader.read_purchase_sheet(purchase_url)
    
    order_list = reader.merge_data(sales_df, purchase_df)
    
    return order_list

