---
description: /order-packing - イーウーパスポートで梱包材を自動発注する
alwaysApply: false
---

# /order-packing コマンド

イーウーパスポートで梱包材（段ボール・緩衝材等）を自動発注する。

## 共通設定

- 作業ディレクトリ: `/Users/wadaatsushi/Documents/automation/procurements/auto-order`
- Python: `/Users/wadaatsushi/Documents/automation/procurements/auto-order/.venv/bin/python`
- 設定ファイル: `.env`

## 実行

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python order_packing_materials.py
```

## 注意事項

- Playwright Chromiumが必要（`playwright install chromium`）
- headless=False で実行される（ブラウザ表示あり）
