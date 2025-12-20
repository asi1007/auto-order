"""
発注情報をマージするService
"""

from typing import List, Dict
from domain.value_objects.sales_sheet import SalesSheet
from domain.value_objects.purchase_info_sheet import PurchaseInfoSheet


class OrderMergeService:
    MINIMUM_ORDER_QUANTITY = 10
    
    def merge(self, sales_sheet: SalesSheet, purchase_info_sheet: PurchaseInfoSheet) -> List[Dict]:
        order_list = []
        
        # ASINでマージ
        for sales_item in sales_sheet.items:
            purchase_item = purchase_info_sheet.get_by_asin(sales_item.asin)
            
            if purchase_item is None:
                continue
            
            # 発注数を計算: 売上/日の発注数 × 仕入情報の1商品辺り発注数
            final_order_quantity = sales_item.order_quantity * purchase_item.quantity_per_item
            
            # 発注条件: 発注数が10以上のみ
            if final_order_quantity < self.MINIMUM_ORDER_QUANTITY:
                continue
            
            # 発注数に応じて最適な価格を選択
            selected_price = purchase_item.get_best_price(final_order_quantity)
            
            order_info = {
                'ASIN': sales_item.asin,
                '商品名': purchase_item.title,
                '購入先URL': purchase_item.purchase_url,
                '色・サイズ等指定': purchase_item.color_size_spec,
                '発注数': int(final_order_quantity),
                '単価': selected_price if selected_price > 0 else (purchase_item.unit_price if purchase_item.unit_price > 0 else ''),
                'chatwork文章': purchase_item.chatwork_message,
                'chatwork添付': purchase_item.chatwork_attachment
            }
            order_list.append(order_info)
        
        # 紐付けできなかったASINを表示
        sales_asins = set(sales_sheet.asins)
        purchase_asins = set(purchase_info_sheet.asins)
        merged_asins = {item['ASIN'] for item in order_list}
        
        unmatched_sales = sales_asins - merged_asins
        if unmatched_sales:
            print(f"警告: 以下のASINは仕入情報シートに存在しません: {unmatched_sales}")
        
        unmatched_purchase = purchase_asins - merged_asins
        if unmatched_purchase:
            print(f"情報: 以下のASINは売上/日シートに存在しません: {unmatched_purchase}")
        
        print(f"✓ {len(order_list)}件の発注データを作成しました（発注数{self.MINIMUM_ORDER_QUANTITY}以上）")
        
        return order_list



