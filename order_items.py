"""
商品発注自動化スクリプト

Googleシートから発注情報を読み込み、イーウーパスポートの注文フォームに自動入力します。
"""

import logging
import os
from dotenv import load_dotenv
from infrastructure import get_order_data, group_orders_by_url, NoOrderDataException, automate_orders, ChatworkClient, validate_config, record_purchase_history


logger = logging.getLogger(__name__)


def order_items():
    # 環境変数を読み込み
    load_dotenv()
    
    # 設定を取得
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    sales_url = os.getenv('SALES_SHEET_URL')
    purchase_url = os.getenv('PURCHASE_SHEET_URL')
    purchase_history_url = os.getenv('PURCHASE_HISTORY_SHEET_URL')
    purchase_history_sheet_name = os.getenv('PURCHASE_HISTORY_SHEET_NAME')
    yiwupassport_email = os.getenv('YIWUPASSPORT_EMAIL')
    yiwupassport_password = os.getenv('YIWUPASSPORT_PASSWORD')
    headless = os.getenv('HEADLESS', 'False').lower() == 'true'
    chatwork_api_token = os.getenv('CHATWORK_API_TOKEN')
    chatwork_room_id = os.getenv('CHATWORK_ROOM_ID', '397092794')
    
    # 設定の検証
    if not validate_config(
        credentials_file,
        yiwupassport_email,
        yiwupassport_password,
        sheet_urls=[sales_url, purchase_url],
        sheet_url_names=['SALES_SHEET_URL', 'PURCHASE_SHEET_URL']
    ):
        return
    
    chatwork_client = ChatworkClient(chatwork_api_token)
    
    try:
        order_list = get_order_data(credentials_file, sales_url, purchase_url)
        order_groups = group_orders_by_url(order_list, max_items_per_group=5)
        
        # ステップ3: ブラウザで注文フォームに自動入力
        logger.info("[ステップ3] 注文フォームに自動入力を開始します...")
        logger.info("-" * 60)
        automate_orders(
            order_groups,
            headless=headless,
            email=yiwupassport_email,
            password=yiwupassport_password,
        )
        
        logger.info("処理が完了しました")
        
        # 購入履歴を記録
        record_purchase_history(
            credentials_file,
            purchase_history_url,
            order_groups,
            purchase_history_sheet_name
        )
        
        # Chatworkに通知を送信（chatwork文章とchatwork添付がある場合のみ）
        for group in order_groups:
            for order in group:
                chatwork_message = order.get('chatwork文章', '').strip()
                chatwork_attachment = order.get('chatwork添付', '').strip()
                asin = order.get('ASIN', '')
                
                chatwork_client.send_order_notification(
                    chatwork_room_id,
                    chatwork_message,
                    chatwork_attachment,
                    asin
                )
        
    except NoOrderDataException:
        return
    except Exception as e:
        logger.exception("エラーが発生しました: %s", e)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    order_items()

