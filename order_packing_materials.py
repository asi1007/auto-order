"""
梱包材発注自動化スクリプト

Googleシートから梱包材の発注情報を読み込み、イーウーパスポートの注文フォームに自動入力します。
"""

import logging
import os
from dotenv import load_dotenv
from infrastructure.repositories.packing_materials_sheet_repository import SheetsPackingMaterialsSheetRepository
from infrastructure import group_orders_by_url, OrderAutomation, NoOrderDataException, validate_config, record_purchase_history


logger = logging.getLogger(__name__)


def convert_packing_materials_to_order_format(packing_materials_item) -> dict:
    assert packing_materials_item is not None, "packing_materials_itemはNoneであってはなりません"
    assert packing_materials_item.material_name, "資材名称は必須です"
    assert packing_materials_item.product_name, "商品名は必須です"
    assert packing_materials_item.url, "URLは必須です"
    assert packing_materials_item.order_quantity > 0, "発注数は0より大きい必要があります"
    
    return {
        'ASIN': packing_materials_item.material_name,
        '資材名称': packing_materials_item.material_name,
        '商品名': packing_materials_item.product_name,
        '購入先URL': packing_materials_item.url,
        '色・サイズ等指定': packing_materials_item.detail,
        '発注数': packing_materials_item.order_quantity,
        'ロットサイズ': packing_materials_item.lot_size,
        '単価': packing_materials_item.price if packing_materials_item.price > 0 else '',
        'chatwork文章': '',
        'chatwork添付': ''
    }


def get_packing_materials_order_data(credentials_file: str, packing_materials_url: str, sheet_name: str = None):
    import logging
    logger = logging.getLogger(__name__)
    
    assert credentials_file, "credentials_fileは必須です"
    assert packing_materials_url, "packing_materials_urlは必須です"
    
    logger.info("[ステップ1] Googleシートから梱包材発注データを読み込んでいます...")
    repository = SheetsPackingMaterialsSheetRepository(credentials_file)
    packing_materials_sheet = repository.read(packing_materials_url, sheet_name or "使用資材")
    assert packing_materials_sheet is not None, "packing_materials_sheetはNoneであってはなりません"
    
    order_list = []
    for item in packing_materials_sheet.items:
        assert item.order_quantity >= 0, f"発注数は0以上である必要があります（商品: {item.product_name}）"
        if item.order_quantity > 0:
            order_info = convert_packing_materials_to_order_format(item)
            order_list.append(order_info)
    
    if not order_list:
        logger.info("処理する発注データがありません（発注数が0より大きい行がありません）")
        raise NoOrderDataException("処理する発注データがありません")
    
    logger.info(f"✓ {len(order_list)}件の梱包材発注データを読み込みました")
    
    assert len(order_list) > 0, "order_listは空であってはなりません"
    
    logger.info("[発注データ一覧]")
    logger.info("-" * 60)
    for i, order in enumerate(order_list, 1):
        assert "商品名" in order, f"order[{i}]に商品名がありません"
        assert "購入先URL" in order, f"order[{i}]に購入先URLがありません"
        assert "発注数" in order, f"order[{i}]に発注数がありません"
        assert order["発注数"] > 0, f"order[{i}]の発注数は0より大きい必要があります"
        
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
    headless = os.getenv('HEADLESS', 'False').lower() == 'true'
    packing_materials_sheet_name = os.getenv('PACKING_MATERIALS_SHEET_NAME')
    automation = OrderAutomation.from_env(headless=headless)
    
    if not validate_config(
        credentials_file,
        sheet_urls=[packing_materials_url],
        sheet_url_names=['PACKING_MATERIALS_SHEET_URL'],
    ):
        return
    
    
    try:
        order_list = get_packing_materials_order_data(credentials_file, packing_materials_url, packing_materials_sheet_name)
        assert order_list, "order_listは空であってはなりません"
        
        order_groups = group_orders_by_url(order_list, max_items_per_group=5)
        assert order_groups, "order_groupsは空であってはなりません"
        
        results = automation.process_orders(order_groups)

        for result in results:
            for order in result.order_group:
                order["注文番号"] = result.order_number or ""
        
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


