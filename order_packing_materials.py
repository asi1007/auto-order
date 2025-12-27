"""
梱包材発注自動化スクリプト

Googleシートから梱包材の発注情報を読み込み、イーウーパスポートの注文フォームに自動入力します。
"""

import logging
import os
from dotenv import load_dotenv
from domain.repositories.sheets_repository import SheetsRepository
from infrastructure import group_orders_by_url, automate_orders, ChatworkClient, NoOrderDataException, validate_config, record_purchase_history


logger = logging.getLogger(__name__)


def convert_packing_materials_to_order_format(packing_materials_item) -> dict:
    return {
        'ASIN': packing_materials_item.product_name,
        '商品名': packing_materials_item.product_name,
        '購入先URL': packing_materials_item.url,
        '色・サイズ等指定': packing_materials_item.detail,
        '発注数': packing_materials_item.order_quantity,
        '単価': packing_materials_item.price if packing_materials_item.price > 0 else '',
        'chatwork文章': '',
        'chatwork添付': ''
    }


def get_packing_materials_order_data(credentials_file: str, packing_materials_url: str, sheet_name: str = None):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("[ステップ1] Googleシートから梱包材発注データを読み込んでいます...")
    logger.info("-" * 60)
    
    repository = SheetsRepository(credentials_file)
    packing_materials_sheet = repository.read_packing_materials_sheet(packing_materials_url, sheet_name)
    
    order_list = []
    for item in packing_materials_sheet.items:
        if item.order_quantity > 0:
            order_info = convert_packing_materials_to_order_format(item)
            order_list.append(order_info)
    
    if not order_list:
        logger.info("処理する発注データがありません（発注数が0より大きい行がありません）")
        raise NoOrderDataException("処理する発注データがありません")
    
    logger.info(f"✓ {len(order_list)}件の梱包材発注データを読み込みました")
    
    logger.info("[発注データ一覧]")
    logger.info("-" * 60)
    for i, order in enumerate(order_list, 1):
        logger.info(
            "  商品%s: %s",
            i,
            order["商品名"],
        )
        logger.info(
            "         URL: %s",
            order["購入先URL"],
        )
        logger.info(
            "         発注数: %s, 単価: %s",
            order["発注数"],
            order["単価"],
        )
        if order["色・サイズ等指定"]:
            logger.info(
                "         詳細: %s",
                order["色・サイズ等指定"],
            )
    
    return order_list


def order_packing_materials():
    load_dotenv()
    
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    packing_materials_url = os.getenv('PACKING_MATERIALS_SHEET_URL')
    purchase_history_url = os.getenv('PURCHASE_HISTORY_SHEET_URL')
    purchase_history_sheet_name = os.getenv('PURCHASE_HISTORY_SHEET_NAME')
    yiwupassport_email = os.getenv('YIWUPASSPORT_EMAIL')
    yiwupassport_password = os.getenv('YIWUPASSPORT_PASSWORD')
    headless = os.getenv('HEADLESS', 'False').lower() == 'true'
    packing_materials_sheet_name = os.getenv('PACKING_MATERIALS_SHEET_NAME')
    
    if not validate_config(
        credentials_file,yiwupassport_email,yiwupassport_password,sheet_urls=[packing_materials_url], sheet_url_names=['PACKING_MATERIALS_SHEET_URL']):
        return
    
    
    try:
        order_list = get_packing_materials_order_data(credentials_file, packing_materials_url, packing_materials_sheet_name)
        order_groups = group_orders_by_url(order_list, max_items_per_group=5)
        
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
        
    except NoOrderDataException:
        return
    except Exception as e:
        logger.exception("エラーが発生しました: %s", e)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    order_packing_materials()

