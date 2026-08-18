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

### 0. Chatwork の資材発注依頼を取り込む【残高確認より前】

倉庫（徐雪蘭さん）から Chatwork ルーム `397092794` に届く「〜が在庫不足ので、再注文してお願いいたします」を拾い、
`使用資材` シートの「発注数」列（Q列）へ数量を書き込む。ここを埋めてからでないと Step 2 の梱包材発注が動かない。

```bash
.venv/bin/python ingest_material_requests.py
```

書き込みはせず、取り込む内容だけを表示する。出力は2つに分かれる。

| 見出し | 意味 | 対応 |
|---|---|---|
| 発注数を書き込む資材 | 資材を一意に特定でき、過去の発注実績から数量も決まったもの | 内容をユーザーに提示して承認を得る |
| 保留・要確認 | 自動で決められなかったもの | 理由ごとに下表の対応をする |

**必ずユーザーに提示して承認を得てから** `--apply` を付けて実行する。勝手に書き込まない。

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python ingest_material_requests.py --apply
```

保留の理由と対応:

| 理由 | 何が起きているか | 対応 |
|---|---|---|
| サイズ表記なし | 依頼文に寸法が無い（画像だけで指示されている等） | Chatwork の該当メッセージと画像をユーザーに見せ、資材と数量を聞く |
| 候補なし | どの資材の「詳細」列とも寸法が一致しない | 資材が未登録か、寸法の書き方が違う。ユーザーに確認する |
| 候補が複数 | 同じ寸法の資材が複数ある（例: OPP袋8 と OPP袋11 はどちらも 32*40） | どちらかをユーザーに聞く |
| 発注実績なし | 発注ログ（Z〜AD列）にその資材の過去発注が無い | 数量をユーザーに聞く |

保留になった依頼は**処理済みとして記録しない**ので、次回の実行でまた出てくる。取りこぼさない。

**導入時・state を作り直したときだけ**、既に人手で発注済みの過去分を消化する。
書き込みはせず、処理済みの記録だけを付ける。

```bash
.venv/bin/python ingest_material_requests.py --seed-before 2026-08-17  # その日より前の依頼だけ
.venv/bin/python ingest_material_requests.py --seed                    # 検出済みを全て
```

**まず `--seed-before` を検討する。** `--seed` は未対応の依頼まで消化してしまう。
Chatwork で「発注しました」と返信済みかを確認し、未対応の依頼が残る日を境にする。
2026-08-18 の導入時は `--seed-before 2026-08-17` で 4件を消化し、未対応の 08/17 の OPP袋依頼だけを残した。

処理済みの記録は `.material_request_state.json`（git 管理外）。**このファイルを消すと過去の依頼を再度発注しかねない**ので消さない。

### 1. 残高確認【発注前に必ず実行】


発注を始める前に、残高が足りているかを必ず確認する。残高不足のまま発注すると、後半のグループが途中で失敗して**部分発注**になり、どこまで通ったかを注文履歴から追う羽目になる。

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python check_balance.py
```

出力される内容: 現在残高（CNY/JPY）、発注対象の明細、商品代金の合計、推奨残高。

終了コードで判断する。

| 終了コード | 意味 | 対応 |
|---|---|---|
| 0 | 残高が足りている（または発注対象なし） | ステップ2へ進む |
| 1 | **残高不足** | 発注を実行しない。不足額をユーザーに報告して指示を仰ぐ |

**推奨残高は商品代金の 1.2 倍**。実際の引き落としは商品代金だけでなく送料・手数料が上乗せされるため。2026-08-10 の発注では商品代金 13,380 元に対し実際は 16,400 元（+3,020 元 / 約1.23倍）が引かれた。商品代金ちょうどの残高では足りない。

JPY 残高がある場合、`order_items.py` が発注前に全額を人民元へ自動両替する。`check_balance.py` は両替前の CNY のみで判定するため、JPY があるのに「残高不足」と出た場合は両替後の額で足りるかを換算して判断する。

### 2. 商品発注

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python order_items.py
```

結果をユーザーに報告する。

### 3. 梱包材発注

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/auto-order && .venv/bin/python order_packing_materials.py
```

結果をユーザーに報告する。

### 4. Obsidian daily note へ記録【必須・省略厳禁】

**ユーザーへの報告で終わらせない。** 発注は実行系タスクであり、いつ何をいくつ発注したかの記録が残らないと後追いができない。ステップ2・3の結果報告と同じターンの中で、必ず daily note へ追記する。

- 追記先: `obsidian/main/daily/YYYY-MM-DD.md` の「## Claude Code ログ」セクション配下（なければ末尾に作成）
- **1セッション1行**。形式は `- **HH:MM** 📦 <50〜70字>`。金額・件数は太字
- 1行に含める: 発注件数、注文番号、発注前後の残高
- 例: `- **10:21** 📦 入金確認後にイーウーで**4商品**発注（\`Y0806-260810001/002\`、残高 **34,086元→17,686元**）`
- 経緯・試行錯誤・商品名の羅列は書かない。詳細は仕入管理シートと注文履歴に残るため不要
- 残高不足で発注を見送った場合や対象0件の場合も、その事実を1行で記録する

ユーザーへのチャット報告では、注文番号・ASIN・**売上/日シート H列の日本語商品名**（中国語の仕入情報題名は使わない）・数量・単価・発注前後残高を表で示す。

## ⚠️ 実行ルール（多重起動事故防止・絶対厳守）

過去に同じスクリプトを並行で2本起動してしまい、17件以上の重複発注が発生した実害あり。以下は例外なく守る。

1. **`.venv/bin/python order_items.py` および `.venv/bin/python order_packing_materials.py` は絶対に多重起動しない**
   - Bash tool の `run_in_background: true` は**使わない**（フォアグラウンドで1本ずつ完了を待つ）
   - `| tail -N` や `| head -N` などのパイプで出力を絞らない → tool 上「出力が空」に見えて再実行を招く。代わりに `> /tmp/order_xxx_$(date +%Y%m%d_%H%M%S).log 2>&1` でファイルにリダイレクトし、完了後に `grep` で抽出する
2. **「動いてないように見える」ときの唯一の許される対処**: まず `ps aux | grep order_items` または `grep order_packing` で確認する。**プロセスが動いていたら絶対に新規起動しない**。動いていなければ、そのあとに限り1本だけ起動する
3. **順序**: `order_items.py` を完了させてから `order_packing_materials.py` を起動する。並行禁止
4. **中断が必要な場合**: `pkill -9 -f "order_items.py"` などで確実に停止させたことを `ps aux` で再確認してから次の操作へ進む

## その他の注意事項

- Playwright Chromiumが必要（`playwright install chromium`）
- headless=False で実行される（ブラウザ表示あり）
- 発注失敗検知: 提出後の注文番号が提出前スナップショットと同一 → 未成立扱い（`order_number=None`）
- 仕入管理・購入履歴には `order_number` が空のグループを記録しないガードあり
- YP側 UI は頻繁に変わるため、`フィールド[XXX]への入力失敗: Timeout` が出たら、`logs/debug/*_fill_failure.html` の placeholder を `grep -o 'placeholder="[^"]*"' | sort -u` で確認して `OrderAutomation.PLACEHOLDER_*` を更新する

## 報告フォーマット指針

商品発注の報告では、実行ログに出力される `product_name`（中国語の仕入情報題名）を使わず、**売上/日シートの`商品名`列（H列）の日本語名** をASINで引いて報告する。詳細は `/order-items` スキル参照。

梱包材発注の `資材名称` は元から日本語のため、そのまま使う。

## 仕入管理シートへの単発追記（過去の発注を後から記録する場合）

例: 「B0F37S31GY 7/4に500こ買った Y0806-260704029 を仕入管理に記載して」のように、後から手動で1件だけ追記を求められるケース。

**絶対条件: `PurchaseManagementItem` の以下フィールドを全て埋めること。省略すると仕入管理シートの備考(A)・納品分類(U)などが空欄になり、実害となる。**

必須で埋めるフィールド:

| フィールド | 対応する仕入管理シート列 | 取得元 |
|---|---|---|
| `purchase_date` | F 購入日 | ユーザー指定 |
| `order_number` | O 注文番号 | ユーザー指定 |
| `asin` | D ASIN | ユーザー指定 |
| `product_name` | E 商品名 | 売上/日シートH列 or 過去の仕入管理レコード |
| `url` | AP 購入先 | 過去の仕入管理レコード |
| `quantity` | Q 購入数 | ユーザー指定 |
| `unit_price` | AS 現地価格(CNY) | 過去の仕入管理レコード AS 列。**同一ASINに補助部材がある場合は全部材を合算した1個あたり実原価**（下記参照） |
| `unit_price_jpy` | AQ 購入価格(JPY) | `infrastructure.exchange_rate_service.convert_cny_to_jpy(unit_price)` |
| **`remark_text`** | **A 備考** | **過去の同ASIN最新レコード A 列（梱包指示。省略厳禁）** |
| **`delivery_category`** | **U 納品分類** | **過去の同ASIN最新レコード U 列（"ノーマル" 等。省略厳禁）** |
| `image_text` | C 画像 | 通常空でOK（数式で自動） |
| `detail` | 該当なし（内部用） | 空でOK |

手順:
1. 対象ASINの過去最新レコードを `PURCHASE_MANAGEMENT_SHEET_URL` から取得（同ASINで直近の行を検索）
2. その行から `remark_text`（col A）, `delivery_category`（col U）, `url`（col AP）, `unit_price`（col AS）, `product_name`（col E）を取得
3. `PurchaseManagementItem` に全フィールドを渡す
4. `SheetsPurchaseManagementRepository.append(item)` を呼ぶ（数式列はこの中で自動コピーされる）

参考コード: `infrastructure/purchase_management_recorder.py` の `_to_purchase_management_items_by_asin` が全フィールドを埋めている見本。単発追記でもこれを踏襲する。

### 原価（AS/AQ列）は同一ASINの全部材を足し算する

1つのASINが**主部材＋補助部材**（例: A4アクリルフレーム 10.60元 ＋ 壁掛け用ワイヤー 0.98元）に分かれて発注されることがある。購入先URLが違うため注文番号は別になるが、仕入管理シートは1行にまとめ、**AS列には主部材の単価ではなく合算後の1個あたり実原価（上例なら 11.58 元）**を入れる。AQ列はその合算値を `convert_cny_to_jpy()` に通す。

- 計算式: `全部材の総額（数量×単価）の合計 ÷ 主部材の数量`
- 自動発注では `_merge_same_asin_across_groups` / `_sum_unit_price_per_main_quantity` が実施済み。単発追記でも同じ値にすること
- 主部材の単価だけを載せると原価が過少になり、利益率が実態より良く見えてしまう
