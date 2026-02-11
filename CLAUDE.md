# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

イーウーパスポート発注自動化システム。Googleシート（売上/日・仕入情報）から発注データを読み込み、Playwrightでイーウーパスポートの注文フォームに自動入力する。発注結果は仕入管理シートに記録し、Chatwork通知も可能。

## コマンド

```bash
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

DDD（ドメイン駆動設計）に基づく3層構造。エントリポイントは `order_items.py`（商品）と `order_packing_materials.py`（梱包材）の2つ。

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
