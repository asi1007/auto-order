本ドキュメントは、`auto-order` の設計（DDDレイヤ、主要フロー、データモデル、Google Sheets連携、拡張方針）をまとめたものです。

### 目的
- Google Sheets（売上/日・仕入情報）から発注対象を生成し、イーウーパスポートへ自動入力して発注する
- 発注結果（注文番号など）を **仕入管理シート** に追記する
- 必要に応じてChatwork通知を送る

---

### 全体アーキテクチャ（DDDレイヤ）
- **domain/**
  - **entities/**: 業務の中心モデル（例: `Order`, `OrderGroup`）
  - **value_objects/**: シート入出力/記録用の値（例: `SalesSheet`, `PurchaseInfoSheet`, `PurchaseManagementItem`, `PurchaseHistoryItem`）
  - **repositories/**: 外部永続化のインターフェース（Protocol）
  - **services/**: ドメインルールに基づく計算/統合（例: `OrderMergeService`）
- **usecases/**
  - アプリケーションの操作単位（例: `GetOrderDataUseCase`, `group_orders_by_url`）
- **infrastructure/**
  - 外部I/O実装（Google Sheets/gspread, Chatwork, Playwright）
  - 起動時設定（`AppConfig`）
  - シート追記（`purchase_management_recorder.py`, `purchase_history_recorder.py`）
- **entrypoint（root scripts）**
  - `order_items.py`: 商品発注のエントリポイント
  - `order_packing_materials.py`: 梱包材発注のエントリポイント

---

### データモデル（中心）
- **Order（domain/entities/order.py）**
  - **ASIN**、**購入先URL**、**発注数**、**単価**、**色/サイズ** 等を保持
  - **Sales由来の情報**も保持（`sales_product_name`, `image_text`, `remark_text`）
- **OrderGroup（domain/entities/order_group.py）**
  - Playwrightで「同一購入先URLごとに最大5商品」を1グループにして処理する単位
  - 発注後に `order_number`（注文番号）を保持

---

### 主フロー（order_items）
1. **設定読み込み**
   - `AppConfig.from_dotenv()` が `.env` / 環境変数を読む
2. **Google Sheetsから発注対象を生成**
   - `infrastructure/sheets_reader.get_order_data()` が
     - `SheetsSalesSheetRepository`（売上/日）
     - `SheetsPurchaseInfoSheetRepository`（仕入情報）
     をUseCaseへ注入して `GetOrderDataUseCase.execute()` を実行
   - `OrderMergeService` が ASIN で突合し、`Order` のリストを生成
3. **購入先URLごとにグループ化**
   - `usecases/group_orders_by_url.group_orders_by_url()` が `Order` を `purchase_url` でまとめ、最大5件で分割
4. **Playwrightで発注処理**
   - `OrderAutomation.process_orders()` が各グループをフォーム入力→送信し、`OrderGroup(order_number=...)` を返す
5. **仕入管理シートに追記（OrderAutomation結果はここへ保存）**
   - `record_purchase_management()` が `OrderGroup` を走査して追記
6. **Chatwork通知（任意）**
   - `ChatworkClient.send_notifications_for_order_groups()`（chatwork文章/添付があるもののみ送信）

---

### ユースケース詳細
この章は「何が入力され、何が返り、どこに副作用があるか」をユースケース単位で定義する。

#### UC-01: 発注データ取得（GetOrderDataUseCase）
- **責務**: 売上/日（Sales）と仕入情報（PurchaseInfo）を読み取り、ASINで突合して `Order` の一覧を生成する
- **入力**
  - `sales_url: str`（売上/日シートURL）
  - `purchase_url: str`（仕入情報シートURL）
  - `sales_sheet_name: str = "売上/日"`
  - `purchase_sheet_name: str = "仕入情報"`
- **出力**
  - `list[Order]`
- **前提**
  - Sales/PurchaseInfoのRepositoryが注入されている（インフラ実装はUseCase外で配線）
  - 両シートは2行目がヘッダー、3行目以降がデータ（現行のSheets実装に依存）
- **ドメインルール**
  - ASINで突合
  - 発注数（計算後）が `OrderMergeService.MINIMUM_ORDER_QUANTITY(=10)` 未満は除外
  - `Order.order_quantity = Sales.order_quantity * PurchaseInfo.quantity_per_item`
  - `Order.sales_product_name` は Salesの「商品名」を優先し、無ければ PurchaseInfoの「題名」を使う
  - `Order.image_text`, `Order.remark_text` は Sales由来の値を保持する
- **例外**
  - `NoOrderDataException`: 生成結果が空の場合
- **副作用**
  - なし（ログ出力のみ）
- **関連実装**
  - `usecases/get_order_data_usecase.py`
  - `domain/services/order_merge_service.py`
  - 配線: `infrastructure/sheets_reader.py`

#### UC-02: 購入先URLごとのグループ化（group_orders_by_url）
- **責務**: `Order.purchase_url` ごとにまとめ、1グループ最大 `max_items_per_group` で分割する
- **入力**
  - `order_list: list[Order]`
  - `max_items_per_group: int = 5`
- **出力**
  - `list[list[Order]]`（購入先URLごと、かつ最大件数で分割済み）
- **前提**
  - `Order.purchase_url` が空でないこと（空の場合はKeyError相当の扱いになるため、上流で担保する）
- **副作用**
  - なし（ログ出力のみ）
- **関連実装**
  - `usecases/group_orders_by_url.py`

#### UC-03: 発注実行（OrderAutomation.process_orders）
- **責務**: Playwrightでイーウーパスポートのフォームに入力し送信、注文番号を取得して `OrderGroup` として返す
- **入力**
  - `order_groups: list[list[Order]]`
- **出力**
  - `list[OrderGroup]`
    - `order_group`: 入力した `Order` のリスト
    - `order_number`: 取得できた注文番号（取得失敗時は `None`）
    - `error`: 例外が起きた場合のメッセージ（現状は一部で設定）
- **前提**
  - `YIWUPASSPORT_EMAIL` / `YIWUPASSPORT_PASSWORD` が設定済み
- **副作用**
  - ブラウザ操作（外部サイトへのアクセス）
- **関連実装**
  - `infrastructure/order_automation.py`

#### UC-04: 仕入管理シート記録（record_purchase_management）
- **責務**: `OrderAutomation` の結果（`list[OrderGroup]`）を走査し、仕入管理シートに追記する
- **入力**
  - `credentials_file: str`
  - `management_sheet_url: str`
  - `order_groups: list[OrderGroup]`（= `process_orders` の戻り）
  - `management_sheet_name: str | None = None`
- **出力**
  - `None`
- **前提**
  - ワークシートは `PURCHASE_MANAGEMENT_SHEET_NAME` で特定（現在の実装は必須想定）
  - ヘッダーは4行目
- **書き込みルール**
  - 商品名列: `Order.sales_product_name`
  - URL列: 購入先列（ヘッダーに `購入先` / `購入先URL` を含む列）
  - 画像列: `画像` を含む列
  - 備考列: `備考` を含む列
- **副作用**
  - Google Sheetsへの追記
- **関連実装**
  - `infrastructure/purchase_management_recorder.py`
  - `infrastructure/repositories/purchase_management_sheet_repository.py`

#### UC-05: 購入履歴シート記録（record_purchase_history）
- **責務**: `OrderAutomation` の結果（`list[OrderGroup]`）から購入履歴として追記する（梱包材等で利用）
- **入力**
  - `credentials_file: str`
  - `history_sheet_url: str`
  - `order_groups: list[OrderGroup]`
  - `sheet_name: str`
- **副作用**
  - Google Sheetsへの追記
- **関連実装**
  - `infrastructure/purchase_history_recorder.py`

#### UC-06: Chatwork通知（send_notifications_for_order_groups）
- **責務**: `Order` の `chatwork_message` / `chatwork_attachment` があるものだけ通知する
- **入力**
  - `order_groups: list[list[Order]]`
- **出力**
  - `None`
- **副作用**
  - Chatwork APIへの送信
- **関連実装**
  - `infrastructure/chatwork_client.py`

### Google Sheets: 入力（読み取り）
#### 売上/日（Sales）
- **Repository**: `infrastructure/repositories/sales_sheet_repository.py`
- **ヘッダーから列名で特定**（見つからない場合は従来通り先頭列を使用）
  - `ASIN`
  - `発注数`（または`注文数`）
  - `商品名`（任意）
  - `画像`（任意）
  - `備考`（任意）

#### 仕入情報（PurchaseInfo）
- **Repository**: `infrastructure/repositories/purchase_info_sheet_repository.py`
- 既存仕様に準拠（ASIN、購入先URL、題名、色・サイズ等指定、1商品辺り発注数、単価、chatwork文章/添付、数量割引列）

---

### Google Sheets: 出力（追記）
#### 仕入管理シート（Purchase Management）
- **Recorder**: `infrastructure/purchase_management_recorder.py`
- **Repository**: `infrastructure/repositories/purchase_management_sheet_repository.py`
- **ワークシート指定**
  - `PURCHASE_MANAGEMENT_SHEET_NAME` があれば **シート名優先**
  - ない場合は `PURCHASE_MANAGEMENT_SHEET_URL` の `gid` でworksheet特定（推奨: どちらか必ず設定）
- **列マッピング方針**
  - **4行目**をヘッダーとして読み取り、ヘッダー名の部分一致で値を埋める
  - 仕入管理の **商品名列** には `Order.sales_product_name`（Salesの商品名）を書き込む
  - URLは **購入先列**（`購入先` / `購入先URL` を含む列）に書き込む
  - 画像は **画像列**（`画像` を含む列）に書き込む
  - 備考は **備考列**（`備考` を含む列）に書き込む

#### 購入履歴シート（Purchase History）
- 現状は梱包材側などで利用。`record_purchase_history()` は `OrderGroup` から `PurchaseHistoryItem` へ変換して追記。

---

### 設定（.env / 環境変数）
`.env` は環境側で管理し、リポジトリには `env.example` を参照用として置く。

主要キー（抜粋）:
- `GOOGLE_CREDENTIALS_FILE`
- `SALES_SHEET_URL`
- `PURCHASE_SHEET_URL`
- `PURCHASE_HISTORY_SHEET_URL` / `PURCHASE_HISTORY_SHEET_NAME`
- `PURCHASE_MANAGEMENT_SHEET_URL`
- `PURCHASE_MANAGEMENT_SHEET_NAME`（例: `仕入管理`）
- `HEADLESS`
- `CHATWORK_API_TOKEN` / `CHATWORK_ROOM_ID`

---

### テスト方針
- `pytest` による自動テスト
- 外部I/O（gspread/Chatwork/Playwright）はモックし、UseCase/Service/Recorderの変換・分岐をユニットテストする

---

### 既存仕様（補足）
より具体的な運用条件やシート概要は `spec.md` を参照。


