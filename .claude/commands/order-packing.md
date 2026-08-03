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

## ⚠️ 多重起動事故防止（絶対厳守）

- `.venv/bin/python order_packing_materials.py` は**フォアグラウンドで1本だけ**実行する。`run_in_background: true` は使わない
- 出力を絞る用途で `| tail -N` `| head -N` を使わない → 出力が空に見えて再起動を誘発する
- 「動いてないように見える」ときは、まず `ps aux | grep order_packing` で存在確認する。**動いている限り再起動禁止**

## 実行

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python order_packing_materials.py > /tmp/order_packing_$(date +%Y%m%d_%H%M%S).log 2>&1
```

必要なログは完了後に `grep -E "ご注文番号|残高|✗|エラー|グループ処理中" /tmp/order_packing_*.log` などで抽出する。

## 注意事項

- Playwright Chromiumが必要（`playwright install chromium`）
- headless=False で実行される（ブラウザ表示あり）
