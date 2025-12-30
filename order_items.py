"""
商品発注自動化スクリプト

Googleシートから発注情報を読み込み、イーウーパスポートの注文フォームに自動入力します。
"""

import logging
from infrastructure import (
    AppConfig,
    get_order_data,
    group_orders_by_url,
    NoOrderDataException,
    OrderAutomation,
    ChatworkClient,
    record_purchase_management,
)


logger = logging.getLogger(__name__)


def order_items():
    config = AppConfig.from_dotenv()
    automation = OrderAutomation.from_env(headless=config.headless)
    chatwork_client = ChatworkClient.from_env()
    assert config.validate(), "設定が不正です（.env/環境変数と認証情報ファイルを確認してください）"
    
    try:
        order_list = get_order_data(config.credentials_file, config.sales_url, config.purchase_url)
        order_groups = group_orders_by_url(order_list, max_items_per_group=5)
        results = automation.process_orders(order_groups)
        
        # 仕入管理シートに記録（OrderAutomation結果はこっちへ保存）
        record_purchase_management(
            config.credentials_file,
            config.purchase_management_sheet_url,
            results,
            config.purchase_management_sheet_name,
        )
        
        chatwork_client.send_notifications_for_order_groups(order_groups)
        
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

