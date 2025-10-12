# イーウーパスポート発注自動化システム

Googleシートから発注情報を読み込み、イーウーパスポートの注文フォームに自動入力するPythonスクリプトです。

## 機能

- Googleシート「売上/日」と「仕入情報」から発注データを読み込み
- ASINで両シートのデータを紐付け
- 発注数を自動計算（売上/日の発注数 × 仕入情報の1商品辺り発注数）
- Playwrightを使用してイーウーパスポートの注文フォームに自動入力
- 各商品ごとに新しいタブで注文フォームを開く

## セットアップ

### 1. 必要なパッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. Playwrightブラウザのインストール

```bash
playwright install chromium
```

### 3. Google Sheets API認証の設定

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを作成または選択
3. Google Sheets APIを有効化
4. 認証情報 → サービスアカウントを作成
5. サービスアカウントのキー（JSON）をダウンロード
6. ダウンロードしたJSONファイルを `credentials.json` として保存
7. Googleシートでサービスアカウントのメールアドレスに閲覧権限を付与

### 4. 環境変数の設定

`.env.example` を `.env` にコピーして編集：

```bash
cp .env.example .env
```

`.env` ファイルを編集して以下の情報を入力してください：

- `GOOGLE_CREDENTIALS_FILE`: Google Sheets API認証情報ファイルのパス
- `SALES_SHEET_URL`: 売上/日シートのURL
- `PURCHASE_SHEET_URL`: 仕入情報シートのURL
- `YIWUPASSPORT_EMAIL`: イーウーパスポートのログインメールアドレス
- `YIWUPASSPORT_PASSWORD`: イーウーパスポートのログインパスワード
- `HEADLESS`: ブラウザを非表示で実行するか（True/False）

## 使用方法

```bash
python main.py
```

スクリプトを実行すると：

1. Googleシートから発注情報を読み込みます
2. ブラウザが起動します
3. イーウーパスポートに自動ログインします
4. 各ASINごとに新しいタブで注文フォームが開きます
5. 商品情報が自動入力されます
6. **注文確認ボタンは自動でクリックされません**（手動で確認・発注してください）

## 注意事項

- 注文確認前に必ず内容を確認してください
- サービスアカウントの認証情報（credentials.json）は絶対に公開しないでください
- `.gitignore` に `credentials.json` と `.env` が含まれていることを確認してください
- **ログイン情報（メールアドレス・パスワード）は`.env`ファイルに保存され、絶対に公開しないでください**

## トラブルシューティング

### Google Sheets APIのエラー
- サービスアカウントにシートへのアクセス権限があるか確認
- credentials.jsonのパスが正しいか確認

### ブラウザが起動しない
- `playwright install chromium` を実行したか確認
- Pythonのバージョンが3.8以上か確認

### データが紐付けられない
- 両シートのASIN列（A列）のフォーマットが一致しているか確認
- ASINに余計なスペースや改行が含まれていないか確認

