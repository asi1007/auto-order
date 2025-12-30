"""
group_orders_by_url関数のテストコード
"""

import pytest
from domain.entities.order import Order
from usecases.group_orders_by_url import group_orders_by_url


class TestGroupOrdersByUrl:
    """グループ化機能のテスト"""
    
    def test_group_orders_single_url(self):
        """単一URLの場合のテスト"""
        order_list = [
            Order(asin="B001", product_name="商品1", purchase_url="http://test.com", order_quantity=10, unit_price=100),
            Order(asin="B002", product_name="商品2", purchase_url="http://test.com", order_quantity=20, unit_price=200),
            Order(asin="B003", product_name="商品3", purchase_url="http://test.com", order_quantity=30, unit_price=300),
        ]
        
        result = group_orders_by_url(order_list)
        
        # 1グループにまとまる
        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0][0].asin == 'B001'
        assert result[0][1].asin == 'B002'
        assert result[0][2].asin == 'B003'
    
    def test_group_orders_multiple_urls(self):
        """複数URLの場合のテスト"""
        order_list = [
            Order(asin="B001", product_name="商品1", purchase_url="http://test1.com", order_quantity=10, unit_price=100),
            Order(asin="B002", product_name="商品2", purchase_url="http://test2.com", order_quantity=20, unit_price=200),
            Order(asin="B003", product_name="商品3", purchase_url="http://test1.com", order_quantity=30, unit_price=300),
            Order(asin="B004", product_name="商品4", purchase_url="http://test2.com", order_quantity=40, unit_price=400),
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
            Order(asin=f"B{i:03d}", product_name=f"商品{i}", purchase_url="http://test.com", order_quantity=i * 10, unit_price=i * 100)
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
            Order(asin="B001", product_name="商品1", purchase_url="http://url1.com", order_quantity=10, unit_price=100),
            Order(asin="B002", product_name="商品2", purchase_url="http://url1.com", order_quantity=20, unit_price=200),
            Order(asin="B003", product_name="商品3", purchase_url="http://url1.com", order_quantity=30, unit_price=300),
            Order(asin="B004", product_name="商品4", purchase_url="http://url1.com", order_quantity=40, unit_price=400),
            Order(asin="B005", product_name="商品5", purchase_url="http://url1.com", order_quantity=50, unit_price=500),
            Order(asin="B006", product_name="商品6", purchase_url="http://url1.com", order_quantity=60, unit_price=600),
            # URL2: 3商品 → 1グループ
            Order(asin="B007", product_name="商品7", purchase_url="http://url2.com", order_quantity=70, unit_price=700),
            Order(asin="B008", product_name="商品8", purchase_url="http://url2.com", order_quantity=80, unit_price=800),
            Order(asin="B009", product_name="商品9", purchase_url="http://url2.com", order_quantity=90, unit_price=900),
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
            Order(asin="B001", product_name="商品1", purchase_url="http://test.com", order_quantity=10, unit_price=100)
        ]
        
        result = group_orders_by_url(order_list)
        
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0].asin == 'B001'
    
    def test_group_orders_url_normalization(self):
        """URL正規化のテスト（空白、末尾スラッシュ）"""
        order_list = [
            Order(asin="B001", product_name="商品1", purchase_url="http://test.com", order_quantity=10, unit_price=100),
            Order(asin="B002", product_name="商品2", purchase_url="http://test.com/", order_quantity=20, unit_price=200),
            Order(asin="B003", product_name="商品3", purchase_url=" http://test.com ", order_quantity=30, unit_price=300),
            Order(asin="B004", product_name="商品4", purchase_url="http://test.com/ ", order_quantity=40, unit_price=400),
        ]
        
        result = group_orders_by_url(order_list)
        
        # すべて同じURLとして認識され、1グループにまとまる
        assert len(result) == 1
        assert len(result[0]) == 4

