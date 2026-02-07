"""
発注情報をマージするService
"""

from domain.entities.order import Order
from domain.value_objects.sales_sheet import SalesSheet
from domain.value_objects.purchase_info_sheet import PurchaseInfoSheet


class OrderMergeService:
    MINIMUM_ORDER_QUANTITY = 10
    
    def merge(self, sales_sheet: SalesSheet, purchase_info_sheet: PurchaseInfoSheet) -> list[Order]:
        order_list: list[Order] = []
        
        # ASINでマージ
        for sales_item in sales_sheet.items:
            purchase_items = purchase_info_sheet.get_by_asin(sales_item.asin)
            
            if not purchase_items:
                continue
            
            # 複数の購買情報がある場合、それぞれに対して発注情報を作成
            for purchase_item in purchase_items:
                # 発注数を計算: 売上/日の発注数 × 仕入情報の1商品辺り発注数
                final_order_quantity = sales_item.order_quantity * purchase_item.quantity_per_item
                
                # 発注条件: 発注数が10以上のみ
                if final_order_quantity < self.MINIMUM_ORDER_QUANTITY:
                    continue
                
                # 発注数に応じて最適な価格を選択
                selected_price = purchase_item.get_best_price(final_order_quantity)
                
                resolved_unit_price: float | None
                if selected_price and selected_price > 0:
                    resolved_unit_price = float(selected_price)
                elif purchase_item.unit_price and purchase_item.unit_price > 0:
                    resolved_unit_price = float(purchase_item.unit_price)
                else:
                    resolved_unit_price = None

                order = Order(
                    asin=sales_item.asin,
                    product_name=purchase_item.title,
                    sales_product_name=sales_item.product_name or purchase_item.title,
                    purchase_url=purchase_item.purchase_url,
                    color_size_spec=purchase_item.color_size_spec,
                    order_quantity=int(final_order_quantity),
                    sales_order_quantity=int(sales_item.order_quantity),
                    unit_price=resolved_unit_price,
                    chatwork_message=purchase_item.chatwork_message,
                    chatwork_attachment=purchase_item.chatwork_attachment,
                    image_text=sales_item.image_text,
                    remark_text=sales_item.remark_text,
                    delivery_category=sales_item.delivery_category,
                    quantity_per_item=int(purchase_item.quantity_per_item),
                )
                order_list.append(order)
        
        # 紐付けできなかったASINを表示
        sales_asins = set(sales_sheet.asins)
        purchase_asins = set(purchase_info_sheet.asins)
        merged_asins = {item.asin for item in order_list}
        
        unmatched_sales = sales_asins - merged_asins
        if unmatched_sales:
            print(f"警告: 以下のASINは仕入情報シートに存在しません: {unmatched_sales}")
        
        unmatched_purchase = purchase_asins - merged_asins
        if unmatched_purchase:
            print(f"情報: 以下のASINは売上/日シートに存在しません: {unmatched_purchase}")
        
        print(f"✓ {len(order_list)}件の発注データを作成しました（発注数{self.MINIMUM_ORDER_QUANTITY}以上）")
        
        return order_list



