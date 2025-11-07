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
            
            if len(data) < 3:
                raise Exception("シートにデータがありません（列名は2行目、データは3行目以降が必要です）")
            
            # DataFrameに変換（列名は2行目、データは3行目以降）
            df = pd.DataFrame(data[2:], columns=data[1])
            
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
                      M列からZ列の数量割引情報も含む（列名は元のシートの列名を保持）
        """
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
            
            # 列インデックスが存在するか確認
            required_columns = [0, 3, 4, 5, 6, 11]
            if len(df.columns) < 12:  # L列(11)にアクセスするには最低12列必要
                raise Exception(f"シートの列数が不足しています。必要: 12列以上, 実際: {len(df.columns)}列")
            
            # 基本情報の列を選択
            df_filtered = df.iloc[:, required_columns].copy()
            df_filtered.columns = ['ASIN', '購入先URL', '題名', '色・サイズ等指定', '1商品辺り発注数', '単価']
            
            # M列からZ列の数量割引情報を取得（列インデックス12-25）
            # 最大26列まで読み込む（Z列まで）
            if len(df.columns) >= 26:
                # M列からZ列（インデックス12-25）を取得し、元の列名を保持
                for col_idx in range(12, 26):
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
            
            return df_filtered
            
        except Exception as e:
            raise Exception(f"「{sheet_name}」シートの読み込みに失敗しました: {e}")
    
    def _extract_minimum_quantity(self, column_name: str) -> float:
        """
        列名から最低数量を抽出する
        
        Args:
            column_name: 列名（例: "10", "50", "100", "500個以上", "600以上"など）
            
        Returns:
            float: 最低数量。抽出できない場合は0を返す
        """
        import re
        # 列名から数値を抽出（最初に見つかった数値を使用）
        # 列名が「500個以上」や「500以上」のような形式でも対応
        match = re.search(r'(\d+)', str(column_name))
        if match:
            return float(match.group(1))
        return 0.0
    
    def _select_best_price(self, order_quantity: int, base_price: float, row: pd.Series) -> float:
        """
        発注数に応じて最適な価格を選択する
        
        Args:
            order_quantity: 発注数
            base_price: 基本単価（L列の単価）
            row: 仕入情報の行データ
            
        Returns:
            float: 選択された価格
        """
        # 基本単価をデフォルトとして設定
        # base_priceが0またはNaNの場合は、数量割引価格のみを検討する
        best_price = base_price if pd.notna(base_price) and base_price > 0 else float('inf')
        
        # M列からZ列の列名を取得（元のDataFrameの列名）
        # purchase_dfの列名から、M列からZ列に相当する列を探す
        # 実際には、read_purchase_sheetで追加された列名を使用
        # sales_dfからマージされた列（発注数、最終発注数など）は除外
        excluded_cols = ['ASIN', '購入先URL', '題名', '色・サイズ等指定', '1商品辺り発注数', '単価', '発注数', '最終発注数']
        bulk_discount_cols = [col for col in row.index if col not in excluded_cols]
        
        applicable_prices = []
        
        for col_name in bulk_discount_cols:
            # 列名から最低数量を抽出
            min_quantity = self._extract_minimum_quantity(col_name)
            
            # 最低数量が0の場合は、数量割引列として扱わない（列名に数値が含まれていない）
            if min_quantity == 0:
                continue
            
            # 発注数が最低数量以上の場合（500と設定されていたら、500以上ならいつでも適用）
            if order_quantity >= min_quantity:
                # その列の価格を取得
                price = row[col_name]
                if pd.notna(price) and price > 0:
                    applicable_prices.append((min_quantity, price))
        
        # 適用可能な価格がある場合、最も安い価格を選択
        if applicable_prices:
            # 価格でソートして最も安いものを選択
            applicable_prices.sort(key=lambda x: x[1])  # 価格でソート
            cheapest_discount_price = applicable_prices[0][1]
            # 基本単価よりも安い場合のみ数量割引価格を使用
            if cheapest_discount_price < best_price:
                best_price = cheapest_discount_price
        
        # best_priceがinfの場合は0を返す
        if best_price == float('inf'):
            best_price = 0.0
        
        return best_price
    
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
        
        # 発注条件: 発注数が10以上のみ
        before_filter_count = len(merged_df)
        merged_df = merged_df[merged_df['最終発注数'] >= 10]
        filtered_count = before_filter_count - len(merged_df)
        
        if filtered_count > 0:
            print(f"情報: 発注数が10未満のため{filtered_count}件を除外しました")
        
        # 辞書のリストに変換
        order_list = []
        for _, row in merged_df.iterrows():
            # 発注数に応じて最適な価格を選択
            base_price = row['単価'] if pd.notna(row['単価']) else 0.0
            order_quantity = int(row['最終発注数'])
            selected_price = self._select_best_price(order_quantity, base_price, row)
            
            order_info = {
                'ASIN': row['ASIN'],
                '商品名': row['題名'],
                '購入先URL': row['購入先URL'],
                '色・サイズ等指定': row['色・サイズ等指定'] if pd.notna(row['色・サイズ等指定']) else '',
                '発注数': order_quantity,
                '単価': selected_price if selected_price > 0 else (base_price if pd.notna(base_price) else '')
            }
            order_list.append(order_info)
        
        print(f"✓ {len(order_list)}件の発注データを作成しました（発注数10以上）")
        
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


def group_orders_by_url(order_list: List[Dict], max_items_per_group: int = 5) -> List[List[Dict]]:
    """
    購入先URLごとに注文をグループ化する
    
    Args:
        order_list: 発注情報のリスト
        max_items_per_group: 1グループあたりの最大商品数（デフォルト: 5）
        
    Returns:
        List[List[Dict]]: 購入先URLごとにグループ化された発注情報のリスト
    """
    from collections import defaultdict
    
    # 購入先URLごとにグループ化（URLを正規化）
    url_groups = defaultdict(list)
    for order in order_list:
        # URLを正規化（前後の空白を削除、末尾のスラッシュを削除）
        normalized_url = order['購入先URL'].strip().rstrip('/')
        url_groups[normalized_url].append(order)
    
    # デバッグ情報: URL別の商品数を表示
    print(f"\n購入先URL別の商品数:")
    for url, orders in url_groups.items():
        print(f"  {url}: {len(orders)}商品")
    
    # 各グループを最大商品数ごとに分割
    grouped_orders = []
    for url, orders in url_groups.items():
        # 最大商品数ごとに分割
        for i in range(0, len(orders), max_items_per_group):
            group = orders[i:i + max_items_per_group]
            grouped_orders.append(group)
    
    total_groups = len(grouped_orders)
    total_items = sum(len(group) for group in grouped_orders)
    print(f"✓ {total_items}件の商品を{total_groups}グループにまとめました")
    
    # グループの詳細を表示
    for i, group in enumerate(grouped_orders, 1):
        url = group[0]['購入先URL']
        print(f"  グループ{i}: {url} ({len(group)}商品)")
    
    return grouped_orders


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

