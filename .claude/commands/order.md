---
description: /order - イーウーパスポートで商品と梱包材を両方自動発注する
alwaysApply: false
---

# /order コマンド

`/order-items` と `/order-packing` を順番に実行する。

## 共通設定

- 作業ディレクトリ: `/Users/wadaatsushi/Documents/automation/procurements/auto-order`
- Python: `/Users/wadaatsushi/Documents/automation/procurements/auto-order/.venv/bin/python`
- 設定ファイル: `.env`

## 手順

### 1. 商品発注

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python order_items.py
```

結果をユーザーに報告する。

### 2. 梱包材発注

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python order_packing_materials.py
```

結果をユーザーに報告する。

## 注意事項

- Playwright Chromiumが必要（`playwright install chromium`）
- headless=False で実行される（ブラウザ表示あり）

## 報告フォーマット指針

商品発注の報告では、実行ログに出力される `product_name`（中国語の仕入情報題名）を使わず、**売上/日シートの`商品名`列（H列）の日本語名** をASINで引いて報告する。詳細は `/order-items` スキル参照。

梱包材発注の `資材名称` は元から日本語のため、そのまま使う。
