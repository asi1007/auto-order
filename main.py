"""
イーウーパスポート発注自動化メインスクリプト

Googleシートから発注情報を読み込み、イーウーパスポートの注文フォームに自動入力します。
"""

import logging
import os
from dotenv import load_dotenv
from sheets_reader import get_order_data, group_orders_by_url
from order_automation import automate_orders


logger = logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger.info("=" * 60)
    logger.info("イーウーパスポート発注自動化システム")
    logger.info("=" * 60)
    
    # 環境変数を読み込み
    load_dotenv()
    
    # 設定を取得
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    sales_url = os.getenv('SALES_SHEET_URL')
    purchase_url = os.getenv('PURCHASE_SHEET_URL')
    yiwupassport_email = os.getenv('YIWUPASSPORT_EMAIL')
    yiwupassport_password = os.getenv('YIWUPASSPORT_PASSWORD')
    headless = os.getenv('HEADLESS', 'False').lower() == 'true'
    
    # 設定の検証
    if not os.path.exists(credentials_file):
        logger.error("エラー: 認証情報ファイル '%s' が見つかりません", credentials_file)
        logger.error("Google Sheets APIの認証情報を設定してください")
        logger.error("詳細はREADME.mdを参照してください")
        return
    
    if not sales_url or not purchase_url:
        logger.error("エラー: 環境変数が正しく設定されていません")
        logger.error(".envファイルにSALES_SHEET_URLとPURCHASE_SHEET_URLを設定してください")
        logger.error("詳細はREADME.mdを参照してください")
        return
    
    if not yiwupassport_email or not yiwupassport_password:
        logger.error("エラー: イーウーパスポートのログイン情報が設定されていません")
        logger.error(".envファイルにYIWUPASSPORT_EMAILとYIWUPASSPORT_PASSWORDを設定してください")
        logger.error("詳細はREADME.mdを参照してください")
        return
    
    try:
        # ステップ1: Googleシートから発注データを取得
        logger.info("")
        logger.info("[ステップ1] Googleシートから発注データを読み込んでいます...")
        logger.info("-" * 60)
        order_list = get_order_data(credentials_file, sales_url, purchase_url)
        
        if not order_list:
            logger.info("")
            logger.info("処理する発注データがありません")
            return
        
        # ステップ2: 購入先URLごとにグループ化
        logger.info("")
        logger.info("[ステップ2] 購入先URLごとにグループ化しています...")
        logger.info("-" * 60)
        order_groups = group_orders_by_url(order_list, max_items_per_group=5)
        
        # 発注データの確認
        logger.info("")
        logger.info("[発注データ一覧]")
        logger.info("-" * 60)
        for i, group in enumerate(order_groups, 1):
            logger.info("")
            logger.info("グループ%s: %s", i, group[0]["購入先URL"])
            for j, order in enumerate(group, 1):
                logger.info(
                    "  商品%s: %s (ASIN: %s)",
                    j,
                    order["商品名"],
                    order["ASIN"],
                )
                logger.info(
                    "         発注数: %s, 単価: %s",
                    order["発注数"],
                    order["単価"],
                )
        
        # ユーザーに確認
        total_items = sum(len(group) for group in order_groups)
        logger.info("")
        logger.info(
            "%sグループ（合計%s商品）の注文を処理します...",
            len(order_groups),
            total_items,
        )
        logger.info("処理を開始します")
        
        # ステップ3: ブラウザで注文フォームに自動入力
        logger.info("")
        logger.info("[ステップ3] 注文フォームに自動入力を開始します...")
        logger.info("-" * 60)
        automate_orders(
            order_groups,
            headless=headless,
            email=yiwupassport_email,
            password=yiwupassport_password,
        )
        
        logger.info("")
        logger.info("処理が完了しました")
        
    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("処理が中断されました")
    except Exception as e:
        logger.exception("エラーが発生しました: %s", e)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()

