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

## ⚠️ 多重起動事故防止（絶対厳守）

- `.venv/bin/python order_items.py` は**フォアグラウンドで1本だけ**実行する。`run_in_background: true` は使わない
- 出力を絞る用途で `| tail -N` `| head -N` を使わない → 出力ファイルが空に見えて再起動を誘発する。代わりに `> /tmp/order_items_$(date +%Y%m%d_%H%M%S).log 2>&1` でリダイレクトし、完了後に `grep` で抽出
- 「動いてないように見える」ときは、まず `ps aux | grep order_items` で存在確認する。**動いている限り再起動禁止**

## 0. 残高確認【必ず最初に実行】

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python check_balance.py
```

終了コード 1（残高不足）なら**発注を実行せず**、不足額をユーザーに報告して指示を仰ぐ。残高不足のまま走らせると後半グループが失敗して部分発注になる。推奨残高は商品代金の 1.2 倍（送料・手数料が上乗せされるため）。詳細は `/order` の「0. 残高確認」参照。

## 実行

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python order_items.py > /tmp/order_items_$(date +%Y%m%d_%H%M%S).log 2>&1
```

必要なログは完了後に `grep -E "ご注文番号|残高|✗|エラー|グループ処理中" /tmp/order_items_*.log` などで抽出する。

## 実行後の記録【必須・省略厳禁】

ユーザーへの報告で終わらせず、同じターン内で Obsidian daily note（`obsidian/main/daily/YYYY-MM-DD.md` の「## Claude Code ログ」配下）へ **1セッション1行**で追記する。形式・記載項目は `/order` の「3. Obsidian daily note へ記録」を参照。対象0件や残高不足で見送った場合もその事実を記録する。

## 処理概要

1. Google Sheetsから発注データ読み取り（売上/仕入情報/仕入管理シート）
2. ASINごとに発注数を集計
3. 購入URLごとにグループ化（最大5商品/フォーム）
4. Playwrightでイーウーパスポートに自動入力
5. 仕入管理シートにASINごと1行で記録（同一ASINが複数注文に分かれた場合は1行に統合）

## 同一ASINの原価は必ず足し算する【自動化済】

仕入情報シートには、**1つのASINに対して複数行（主部材＋補助部材）**が登録されていることがある。

例: `B0FCHM6QQR` A4アクリルフォトフレーム（摆挂两用款）
| 仕入情報 | 商品 | 単価 |
|---|---|---|
| 主部材 | 摆挂两用款 A4アクリルフレーム | 10.60 元 |
| 補助部材 | 钢丝绳（壁掛け用ワイヤー） | 0.98 元 |

これらは購入先URLが違うため**別々の注文番号**になるが、仕入管理シートには**1行**で記録する。
このとき **AS列(現地価格CNY)・AQ列(購入価格JPY)は主部材の単価ではなく、全部材を合算した「1個あたり実原価」**（上例なら **11.58 元**）を入れる。主部材の単価だけを載せると原価が過少になり、利益計算が狂う。

- 実装: `_merge_same_asin_across_groups` / `_sum_unit_price_per_main_quantity`（[infrastructure/purchase_management_recorder.py](infrastructure/purchase_management_recorder.py)）
- 計算式: `全部材の総額（数量×単価）の合計 ÷ 主部材の数量`。補助部材が主部材と同数なら単純な足し算と一致し、1商品に2本使う等で数量が違っても正しくスケールする
- 数量・納品分類・売値は「総額が最大の item」＝主部材から採用。注文番号とURLは改行区切りで併記
- **手作業で仕入管理シートに追記するときも同じルールを適用する**（下の単発追記セクション参照）

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
