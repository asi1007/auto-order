---
description: /order-items - イーウーパスポートで商品を自動発注する（Googleシートから発注データを集計しPlaywrightで注文フォームに自動入力）
alwaysApply: false
---

# /order-items コマンド

GoogleシートからASINベースで発注数を集計し、Playwrightでイーウーパスポートの注文フォームに自動入力する。

## 共通設定

- 作業ディレクトリ: `/Users/wadaatsushi/Documents/automation/procurements/auto-order`
- Python: `/Users/wadaatsushi/Documents/automation/procurements/auto-order/.venv/bin/python`
- 設定ファイル: `.env`

## 実行

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python order_items.py
```

## 処理概要

1. Google Sheetsから発注データ読み取り（売上/仕入情報/仕入管理シート）
2. ASINごとに発注数を集計
3. 購入URLごとにグループ化（最大5商品/フォーム）
4. Playwrightでイーウーパスポートに自動入力

## DDD構成

- `domain/entities/` — Order, OrderGroup
- `domain/value_objects/` — SalesSheet, PurchaseInfoSheet等
- `domain/services/` — OrderMergeService
- `usecases/` — GetOrderDataUseCase
- `infrastructure/` — gspread実装, Playwright自動化, Chatwork通知

## テスト

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python -m pytest
```

## 注意事項

- 最小発注数: 10個以上（計算後）
- Playwright Chromiumが必要（`playwright install chromium`）
- headless=False で実行される（ブラウザ表示あり）

## 報告フォーマット指針

実行ログには `product_name`（仕入情報シートの`題名`＝1688の中国語）が出力されるが、**ユーザー向け報告では中国語名を転載しない**。

代わりに **売上/日シートの`商品名`列（4行目ヘッダー、H列）の日本語名** を使う。ASINで照合して引く。

参考:
- ヘッダー検出: `ASIN` + `発注数` がある行が4行目（1行目の `ASIN_SELL` `TITLE_SELL` は別ヘッダーなので注意）
- コード上は `Order.sales_product_name` に同じ値が入る設計（`OrderMergeService` 参照）
