"""
group_orders_by_url関数のテストコード
"""

import pytest
from sheets_reader import group_orders_by_url


class TestGroupOrdersByUrl:
    """グループ化機能のテスト"""
    
    def test_group_orders_single_url(self):
        """単一URLの場合のテスト"""
        order_list = [
            {'ASIN': 'B001', '商品名': '商品1', '購入先URL': 'http://test.com', '発注数': 10, '単価': 100},
            {'ASIN': 'B002', '商品名': '商品2', '購入先URL': 'http://test.com', '発注数': 20, '単価': 200},
            {'ASIN': 'B003', '商品名': '商品3', '購入先URL': 'http://test.com', '発注数': 30, '単価': 300},
        ]
        
        result = group_orders_by_url(order_list)
        
        # 1グループにまとまる
        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0][0]['ASIN'] == 'B001'
        assert result[0][1]['ASIN'] == 'B002'
        assert result[0][2]['ASIN'] == 'B003'
    
    def test_group_orders_multiple_urls(self):
        """複数URLの場合のテスト"""
        order_list = [
            {'ASIN': 'B001', '商品名': '商品1', '購入先URL': 'http://test1.com', '発注数': 10, '単価': 100},
            {'ASIN': 'B002', '商品名': '商品2', '購入先URL': 'http://test2.com', '発注数': 20, '単価': 200},
            {'ASIN': 'B003', '商品名': '商品3', '購入先URL': 'http://test1.com', '発注数': 30, '単価': 300},
            {'ASIN': 'B004', '商品名': '商品4', '購入先URL': 'http://test2.com', '発注数': 40, '単価': 400},
        ]
        
        result = group_orders_by_url(order_list)
        
        # 2グループに分かれる
        assert len(result) == 2
        
        # 各グループに2商品ずつ
        assert len(result[0]) == 2
        assert len(result[1]) == 2
    
    def test_group_orders_max_items_per_group(self):
        """最大商品数を超える場合のテスト"""
        order_list = [
            {'ASIN': f'B{i:03d}', '商品名': f'商品{i}', '購入先URL': 'http://test.com', 
             '発注数': i*10, '単価': i*100}
            for i in range(1, 8)  # 7商品
        ]
        
        result = group_orders_by_url(order_list, max_items_per_group=5)
        
        # 5商品+2商品の2グループに分かれる
        assert len(result) == 2
        assert len(result[0]) == 5
        assert len(result[1]) == 2
    
    def test_group_orders_complex_scenario(self):
        """複雑なシナリオのテスト"""
        order_list = [
            # URL1: 6商品 → 5+1に分割
            {'ASIN': 'B001', '商品名': '商品1', '購入先URL': 'http://url1.com', '発注数': 10, '単価': 100},
            {'ASIN': 'B002', '商品名': '商品2', '購入先URL': 'http://url1.com', '発注数': 20, '単価': 200},
            {'ASIN': 'B003', '商品名': '商品3', '購入先URL': 'http://url1.com', '発注数': 30, '単価': 300},
            {'ASIN': 'B004', '商品名': '商品4', '購入先URL': 'http://url1.com', '発注数': 40, '単価': 400},
            {'ASIN': 'B005', '商品名': '商品5', '購入先URL': 'http://url1.com', '発注数': 50, '単価': 500},
            {'ASIN': 'B006', '商品名': '商品6', '購入先URL': 'http://url1.com', '発注数': 60, '単価': 600},
            # URL2: 3商品 → 1グループ
            {'ASIN': 'B007', '商品名': '商品7', '購入先URL': 'http://url2.com', '発注数': 70, '単価': 700},
            {'ASIN': 'B008', '商品名': '商品8', '購入先URL': 'http://url2.com', '発注数': 80, '単価': 800},
            {'ASIN': 'B009', '商品名': '商品9', '購入先URL': 'http://url2.com', '発注数': 90, '単価': 900},
        ]
        
        result = group_orders_by_url(order_list, max_items_per_group=5)
        
        # 合計3グループ（URL1: 2グループ、URL2: 1グループ）
        assert len(result) == 3
        
        # 合計商品数は変わらない
        total_items = sum(len(group) for group in result)
        assert total_items == 9
    
    def test_group_orders_empty_list(self):
        """空リストの場合のテスト"""
        result = group_orders_by_url([])
        
        assert len(result) == 0
    
    def test_group_orders_single_item(self):
        """1商品のみの場合のテスト"""
        order_list = [
            {'ASIN': 'B001', '商品名': '商品1', '購入先URL': 'http://test.com', '発注数': 10, '単価': 100}
        ]
        
        result = group_orders_by_url(order_list)
        
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0]['ASIN'] == 'B001'
    
    def test_group_orders_url_normalization(self):
        """URL正規化のテスト（空白、末尾スラッシュ）"""
        order_list = [
            {'ASIN': 'B001', '商品名': '商品1', '購入先URL': 'http://test.com', '発注数': 10, '単価': 100},
            {'ASIN': 'B002', '商品名': '商品2', '購入先URL': 'http://test.com/', '発注数': 20, '単価': 200},
            {'ASIN': 'B003', '商品名': '商品3', '購入先URL': ' http://test.com ', '発注数': 30, '単価': 300},
            {'ASIN': 'B004', '商品名': '商品4', '購入先URL': 'http://test.com/ ', '発注数': 40, '単価': 400},
        ]
        
        result = group_orders_by_url(order_list)
        
        # すべて同じURLとして認識され、1グループにまとまる
        assert len(result) == 1
        assert len(result[0]) == 4

