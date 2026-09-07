# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

イーウーパスポート発注自動化システム。Googleシート（売上/日・仕入情報）から発注データを読み込み、Playwrightでイーウーパスポートの注文フォームに自動入力する。発注結果は仕入管理シートに記録し、Chatwork通知も可能。

## コマンド

```bash
# 残高確認（発注前に必ず実行。終了コード1=残高不足）
python check_balance.py

# 商品発注
python order_items.py

# 梱包材発注
python order_packing_materials.py

# テスト実行
pytest

# 単一テストファイル
pytest tests/test_sheets_reader.py

# 単一テスト関数
pytest tests/test_sheets_reader.py::TestClassName::test_function_name

# 依存パッケージインストール
pip install -r requirements.txt

# デプロイ（/deploy スキルで実行）
# git commit → git push → clasp push
```

## アーキテクチャ

DDD（ドメイン駆動設計）に基づく3層構造。エントリポイントは `order_items.py`（商品）、`order_packing_materials.py`（梱包材）、`check_balance.py`（発注前の残高確認）の3つ。

### 残高不足で発注してはならない

残高不足のまま `order_items.py` を走らせると、後半のグループが途中で失敗して**部分発注**になる。発注前に必ず `check_balance.py` を実行する。

**推奨残高は商品代金の 1.2 倍**（`SAFETY_MARGIN_RATE`）。実際の引き落としには送料・手数料が上乗せされるため、商品代金ちょうどでは足りない。2026-08-10 の発注では商品代金 13,380 元に対し実際は 16,400 元が引かれた。

### 発注フォームでは必ず「マッチ」を押す

倉庫（買付担当）から 2026-09-04 に依頼があった。手動注文フォームに打ち込んだ文字は 1688 と
紐付いていないため、店舗・商品・規格の特定に手間がかかる。`_match_order_item` が3つとも押す。

| マッチ | 挙動 |
|---|---|
| 店舗名マッチ | 1クリックで 1688 の正式店舗名に置換（例: 义乌众邦光学仪器有限公司） |
| 商品名マッチ | 1クリックで 1688 の商品名（日本語訳）に置換 |
| 仕様マッチ | ダイアログが開く。規格を選んで「確認」すると仕様名・単価・仕様画像が同期される |

**マッチは `button` ではなく `div`。** `button:has-text()` では掴めない。`div:text-is("店舗名マッチ")` を使う。
入力欄が空のうちは DOM に存在せず、値を入れると現れる。

**規格は完全一致か「区切りの一区画と完全一致」でしか選ばない。** 仕入情報シートの
「色・サイズ等指定」は 1688 の規格名の一部しか持たないことが多い
（シート `1号【白毛】` / 1688 `画刷-1号【白毛】-尼龙毛`）。部分一致にすると
`1号【白毛】` が `11号【白毛】` を巻き込むため、`-` `/` 等で割った区画の完全一致だけを許す。
候補が1つしかない場合は無条件で選ぶ（その規格しか買えないため）。
一致しなければキャンセルしてテキストのまま提出する。**マッチの失敗で発注は止めない。**

実データ8商品で確認したところ7件が一致した（2026-09-04）。外れたのは 1688 側がサイズのみ
（`XS` `S` …）でシートが `白色S` と色を含んでいたケース。

**規格を紐付けると YP が 1688 の価格で単価を上書きする。** 残高確認（`check_balance.py`）も
仕入管理への記録も仕入情報シートの単価で組んであるため、`_restore_unit_price` がシートの値へ
戻している。差があった場合は WARNING に両方の値を出す。

### レイヤー構成

- **domain/entities/**: `Order`（発注情報）、`OrderGroup`（注文番号付きグループ）
- **domain/value_objects/**: 各Googleシートの構造を表す値オブジェクト（`SalesSheet`, `PurchaseInfoSheet`, `PurchaseManagement` 等）
- **domain/repositories/**: 外部永続化のインターフェース（`Protocol`で定義）
- **domain/services/**: `OrderMergeService` — 売上/日と仕入情報をASINで突合し発注データを生成
- **usecases/**: `GetOrderDataUseCase`（発注データ取得）、`group_orders_by_url`（URL別グループ化）
- **infrastructure/**: 外部I/O実装 — gspreadによるGoogleシート操作、Playwrightによるブラウザ自動化、Chatwork通知

### 主要フロー（商品発注）

1. `.env` から設定読み込み（`AppConfig.from_dotenv()`）
2. Googleシート2枚（売上/日・仕入情報）をASINで突合 → 発注数計算（発注数 × 1商品辺り発注数、10以上のみ対象）
3. 同一購入先URLでグループ化（最大5商品/グループ）
4. Playwrightでイーウーパスポートのフォームに自動入力（`OrderAutomation.process_orders`）
5. 仕入管理シートに結果を記録
6. 発注完了分のASINの発注数をクリア
7. Chatwork通知

### リポジトリパターン

`domain/repositories/` に `Protocol` でインターフェースを定義し、`infrastructure/repositories/` に gspread を使った実装を配置。`BaseSheetsRepository` が gspread クライアントの初期化を担当し、各リポジトリがこれを継承。

## 環境変数（.env）

`env.example` を参照。主要な変数:
- `GOOGLE_CREDENTIALS_FILE`: Google Sheets認証情報ファイルパス
- `SALES_SHEET_URL`, `PURCHASE_SHEET_URL`, `PURCHASE_MANAGEMENT_SHEET_URL`: 各シートURL
- `PURCHASE_MANAGEMENT_SHEET_NAME`: 仕入管理ワークシート名
- `YIWUPASSPORT_EMAIL`, `YIWUPASSPORT_PASSWORD`: イーウーパスポートログイン情報
- `HEADLESS`: ブラウザ表示制御（True/False）
- `CHATWORK_API_TOKEN`, `CHATWORK_ROOM_ID`: Chatwork通知設定（オプション）
- `PACKING_MATERIALS_SHEET_URL`, `PURCHASE_HISTORY_SHEET_URL`: 梱包材関連シートURL

## テスト

pytestを使用。外部I/O（gspread, Playwright, Chatwork）はモック化してテスト。テストは `tests/` ディレクトリに配置。
