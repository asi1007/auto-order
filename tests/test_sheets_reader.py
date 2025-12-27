"""
sheets_reader.pyのテストコード
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from infrastructure.sheets_reader import SheetsReader


class TestSheetsReader:
    """SheetsReaderクラスのテスト"""
    
    @pytest.fixture
    def mock_credentials(self, mocker):
        """認証情報のモック"""
        mock_creds = mocker.patch('infrastructure.sheets_reader.ServiceAccountCredentials.from_json_keyfile_name')
        return mock_creds
    
    @pytest.fixture
    def mock_client(self, mocker):
        """gspreadクライアントのモック"""
        mock_client = mocker.patch('infrastructure.sheets_reader.gspread.authorize')
        return mock_client
    
    @pytest.fixture
    def sheets_reader(self, mock_credentials, mock_client):
        """SheetsReaderインスタンス"""
        return SheetsReader('dummy_credentials.json')
    
    def test_initialization(self, mock_credentials, mock_client):
        """初期化のテスト"""
        reader = SheetsReader('test_credentials.json')
        assert reader.credentials_file == 'test_credentials.json'
        assert reader.client is not None
    
    def test_read_sales_sheet_success(self, sheets_reader, mocker):
        """売上/日シートの読み込み成功のテスト"""
        # モックデータの準備（列名は2行目）
        mock_worksheet = Mock()
        mock_worksheet.get_all_values.return_value = [
            ['1行目（無視）'],  # 1行目は無視される
            ['ASIN', '発注数'],  # 2行目が列名
            ['B001', '10'],  # 3行目以降がデータ
            ['B002', '20'],
            ['B003', '15']
        ]
        
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        
        sheets_reader.client.open_by_url = Mock(return_value=mock_spreadsheet)
        
        # テスト実行
        result = sheets_reader.read_sales_sheet('https://test.url')
        
        # 検証
        assert len(result) == 3
        assert 'ASIN' in result.columns
        assert '発注数' in result.columns
        assert result['ASIN'].tolist() == ['B001', 'B002', 'B003']
        assert result['発注数'].tolist() == [10, 20, 15]
    
    def test_read_sales_sheet_empty_data(self, sheets_reader, mocker):
        """空データのテスト"""
        mock_worksheet = Mock()
        mock_worksheet.get_all_values.return_value = [
            ['1行目（無視）'],  # 1行目は無視される
            ['ASIN', '発注数']  # 2行目が列名だが、データ行がない
        ]
        
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        
        sheets_reader.client.open_by_url = Mock(return_value=mock_spreadsheet)
        
        # 例外が発生することを検証
        with pytest.raises(Exception) as exc_info:
            sheets_reader.read_sales_sheet('https://test.url')
        
        assert 'シートにデータがありません' in str(exc_info.value)
    
    def test_read_purchase_sheet_success(self, sheets_reader, mocker):
        """仕入情報シートの読み込み成功のテスト"""
        # モックデータの準備（12列以上必要、列名は2行目）
        mock_worksheet = Mock()
        mock_worksheet.get_all_values.return_value = [
            ['1行目（無視）'],  # 1行目は無視される
            ['ASIN', 'Col2', 'Col3', '購入先URL', '題名', '色・サイズ', '発注数', 'Col8', 'Col9', 'Col10', 'Col11', '単価'],  # 2行目が列名
            ['B001', '', '', 'http://test1.com', '商品1', 'Red/M', '5', '', '', '', '', '100'],  # 3行目以降がデータ
            ['B002', '', '', 'http://test2.com', '商品2', 'Blue/L', '10', '', '', '', '', '200'],
        ]
        
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        
        sheets_reader.client.open_by_url = Mock(return_value=mock_spreadsheet)
        
        # テスト実行
        result = sheets_reader.read_purchase_sheet('https://test.url')
        
        # 検証
        assert len(result) == 2
        assert 'ASIN' in result.columns
        assert '購入先URL' in result.columns
        assert '題名' in result.columns
        assert result['ASIN'].tolist() == ['B001', 'B002']
    
    def test_merge_data_success(self, sheets_reader):
        """データ結合のテスト"""
        # テストデータの準備
        sales_df = pd.DataFrame({
            'ASIN': ['B001', 'B002', 'B003'],
            '発注数': [10, 20, 15]
        })
        
        purchase_df = pd.DataFrame({
            'ASIN': ['B001', 'B002'],
            '購入先URL': ['http://test1.com', 'http://test2.com'],
            '題名': ['商品1', '商品2'],
            '色・サイズ等指定': ['Red/M', 'Blue/L'],
            '1商品辺り発注数': [5, 10],
            '単価': [100, 200]
        })
        
        # テスト実行
        result = sheets_reader.merge_data(sales_df, purchase_df)
        
        # 検証
        assert len(result) == 2
        assert result[0]['ASIN'] == 'B001'
        assert result[0]['発注数'] == 50  # 10 * 5
        assert result[1]['ASIN'] == 'B002'
        assert result[1]['発注数'] == 200  # 20 * 10
    
    def test_merge_data_no_match(self, sheets_reader):
        """紐付けできないデータのテスト"""
        sales_df = pd.DataFrame({
            'ASIN': ['B001', 'B002'],
            '発注数': [10, 20]
        })
        
        purchase_df = pd.DataFrame({
            'ASIN': ['B003', 'B004'],
            '購入先URL': ['http://test1.com', 'http://test2.com'],
            '題名': ['商品1', '商品2'],
            '色・サイズ等指定': ['Red/M', 'Blue/L'],
            '1商品辺り発注数': [5, 10],
            '単価': [100, 200]
        })
        
        # テスト実行
        result = sheets_reader.merge_data(sales_df, purchase_df)
        
        # 検証：紐付けできるデータがない
        assert len(result) == 0
    
    def test_merge_data_calculation(self, sheets_reader):
        """発注数計算のテスト"""
        sales_df = pd.DataFrame({
            'ASIN': ['B001'],
            '発注数': [12]
        })
        
        purchase_df = pd.DataFrame({
            'ASIN': ['B001'],
            '購入先URL': ['http://test.com'],
            '題名': ['テスト商品'],
            '色・サイズ等指定': ['L'],
            '1商品辺り発注数': [3],
            '単価': [150]
        })
        
        # テスト実行
        result = sheets_reader.merge_data(sales_df, purchase_df)
        
        # 検証：12 * 3 = 36
        assert result[0]['発注数'] == 36
        assert result[0]['商品名'] == 'テスト商品'
        assert result[0]['単価'] == 150
    
    def test_merge_data_filter_minimum_quantity(self, sheets_reader):
        """発注数10以上フィルタのテスト"""
        sales_df = pd.DataFrame({
            'ASIN': ['B001', 'B002', 'B003'],
            '発注数': [5, 10, 3]  # 5*2=10(OK), 10*2=20(OK), 3*2=6(NG)
        })
        
        purchase_df = pd.DataFrame({
            'ASIN': ['B001', 'B002', 'B003'],
            '購入先URL': ['http://test1.com', 'http://test2.com', 'http://test3.com'],
            '題名': ['商品1', '商品2', '商品3'],
            '色・サイズ等指定': ['Red', 'Blue', 'Green'],
            '1商品辺り発注数': [2, 2, 2],
            '単価': [100, 200, 300]
        })
        
        # テスト実行
        result = sheets_reader.merge_data(sales_df, purchase_df)
        
        # 検証：発注数10以上のみ（B001=10, B002=20）、B003=6は除外
        assert len(result) == 2
        assert result[0]['ASIN'] == 'B001'
        assert result[0]['発注数'] == 10
        assert result[1]['ASIN'] == 'B002'
        assert result[1]['発注数'] == 20
    
    def test_merge_data_all_below_minimum(self, sheets_reader):
        """すべて発注数10未満の場合のテスト"""
        sales_df = pd.DataFrame({
            'ASIN': ['B001', 'B002'],
            '発注数': [2, 3]
        })
        
        purchase_df = pd.DataFrame({
            'ASIN': ['B001', 'B002'],
            '購入先URL': ['http://test1.com', 'http://test2.com'],
            '題名': ['商品1', '商品2'],
            '色・サイズ等指定': ['Red', 'Blue'],
            '1商品辺り発注数': [2, 2],
            '単価': [100, 200]
        })
        
        # テスト実行
        result = sheets_reader.merge_data(sales_df, purchase_df)
        
        # 検証：すべて10未満なので結果は空
        assert len(result) == 0
    
    def test_bulk_discount_price_selection(self, sheets_reader):
        """数量割引価格選択のテスト（B0F9WPDW92で600個発注）"""
        sales_df = pd.DataFrame({
            'ASIN': ['B0F9WPDW92'],
            '発注数': [100]  # 100 * 6 = 600個になるように設定
        })
        
        # 仕入情報シートのデータ（M列からZ列に数量割引情報を含む）
        # 複数の数量割引階層がある場合を想定
        # 500個以上: 5.8、600個以上: 5.5
        purchase_df = pd.DataFrame({
            'ASIN': ['B0F9WPDW92'],
            '購入先URL': ['http://test.com'],
            '題名': ['テスト商品'],
            '色・サイズ等指定': [''],
            '1商品辺り発注数': [6],  # 100 * 6 = 600個
            '単価': [10.0],  # 基本単価
            '500': [5.8],   # 500個以上で5.8
            '600': [5.5]   # 600個以上で5.5
        })
        
        # テスト実行
        result = sheets_reader.merge_data(sales_df, purchase_df)
        
        # 検証：600個発注で価格が5.5になる（5.8ではなく5.5が選択される）
        assert len(result) == 1
        assert result[0]['ASIN'] == 'B0F9WPDW92'
        assert result[0]['発注数'] == 600
        assert result[0]['単価'] == 5.5  # 最も安い価格が選択される
    
    def test_bulk_discount_price_selection_multiple_tiers(self, sheets_reader):
        """複数の数量割引階層がある場合のテスト"""
        sales_df = pd.DataFrame({
            'ASIN': ['B001'],
            '発注数': [20]  # 20 * 5 = 100個になるように設定
        })
        
        # 複数の数量割引階層がある場合
        purchase_df = pd.DataFrame({
            'ASIN': ['B001'],
            '購入先URL': ['http://test.com'],
            '題名': ['テスト商品'],
            '色・サイズ等指定': [''],
            '1商品辺り発注数': [5],  # 20 * 5 = 100個
            '単価': [10.0],  # 基本単価
            '50': [8.0],   # 50個以上で8.0
            '100': [6.0],  # 100個以上で6.0
            '200': [5.0]   # 200個以上で5.0
        })
        
        # テスト実行
        result = sheets_reader.merge_data(sales_df, purchase_df)
        
        # 検証：100個発注なので、100個以上の階層（6.0）が適用される
        assert len(result) == 1
        assert result[0]['ASIN'] == 'B001'
        assert result[0]['発注数'] == 100
        assert result[0]['単価'] == 6.0
    
    def test_bulk_discount_price_selection_below_minimum(self, sheets_reader):
        """数量割引の最低数量に満たない場合のテスト"""
        sales_df = pd.DataFrame({
            'ASIN': ['B001'],
            '発注数': [10]  # 10 * 1 = 10個になるように設定
        })
        
        purchase_df = pd.DataFrame({
            'ASIN': ['B001'],
            '購入先URL': ['http://test.com'],
            '題名': ['テスト商品'],
            '色・サイズ等指定': [''],
            '1商品辺り発注数': [1],  # 10 * 1 = 10個
            '単価': [10.0],  # 基本単価
            '50': [8.0],   # 50個以上で8.0
            '100': [6.0]   # 100個以上で6.0
        })
        
        # テスト実行
        result = sheets_reader.merge_data(sales_df, purchase_df)
        
        # 検証：10個発注なので、数量割引は適用されず基本単価（10.0）が適用される
        assert len(result) == 1
        assert result[0]['ASIN'] == 'B001'
        assert result[0]['発注数'] == 10
        assert result[0]['単価'] == 10.0

