"""
イーウーパスポート発注自動化メインスクリプト

Googleシートから発注情報を読み込み、イーウーパスポートの注文フォームに自動入力します。
"""

import os
from dotenv import load_dotenv
from sheets_reader import get_order_data, group_orders_by_url
from order_automation import automate_orders


def main():
    """メイン処理"""
    print("="*60)
    print("イーウーパスポート発注自動化システム")
    print("="*60)
    
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
        print(f"エラー: 認証情報ファイル '{credentials_file}' が見つかりません")
        print("Google Sheets APIの認証情報を設定してください")
        print("詳細はREADME.mdを参照してください")
        return
    
    if not sales_url or not purchase_url:
        print("エラー: 環境変数が正しく設定されていません")
        print(".envファイルにSALES_SHEET_URLとPURCHASE_SHEET_URLを設定してください")
        print("詳細はREADME.mdを参照してください")
        return
    
    if not yiwupassport_email or not yiwupassport_password:
        print("エラー: イーウーパスポートのログイン情報が設定されていません")
        print(".envファイルにYIWUPASSPORT_EMAILとYIWUPASSPORT_PASSWORDを設定してください")
        print("詳細はREADME.mdを参照してください")
        return
    
    try:
        # ステップ1: Googleシートから発注データを取得
        print("\n[ステップ1] Googleシートから発注データを読み込んでいます...")
        print("-" * 60)
        order_list = get_order_data(credentials_file, sales_url, purchase_url)
        
        if not order_list:
            print("\n処理する発注データがありません")
            return
        
        # ステップ2: 購入先URLごとにグループ化
        print("\n[ステップ2] 購入先URLごとにグループ化しています...")
        print("-" * 60)
        order_groups = group_orders_by_url(order_list, max_items_per_group=5)
        
        # 発注データの確認
        print("\n[発注データ一覧]")
        print("-" * 60)
        for i, group in enumerate(order_groups, 1):
            print(f"\nグループ{i}: {group[0]['購入先URL']}")
            for j, order in enumerate(group, 1):
                print(f"  商品{j}: {order['商品名']} (ASIN: {order['ASIN']})")
                print(f"         発注数: {order['発注数']}, 単価: {order['単価']}")
        
        # ユーザーに確認
        total_items = sum(len(group) for group in order_groups)
        print("\n" + "-" * 60)
        response = input(f"\n{len(order_groups)}グループ（合計{total_items}商品）の注文を処理しますか？ (y/N): ")
        if response.lower() != 'y':
            print("処理をキャンセルしました")
            return
        
        # ステップ3: ブラウザで注文フォームに自動入力
        print("\n[ステップ3] 注文フォームに自動入力を開始します...")
        print("-" * 60)
        automate_orders(order_groups, headless=headless, email=yiwupassport_email, password=yiwupassport_password)
        
        print("\n処理が完了しました")
        
    except KeyboardInterrupt:
        print("\n\n処理が中断されました")
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

