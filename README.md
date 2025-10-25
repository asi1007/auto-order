# イーウーパスポート発注自動化システム

Googleシートから発注情報を読み込み、イーウーパスポートの注文フォームに自動入力するPythonスクリプトです。

## 機能

- Googleシート「売上/日」と「仕入情報」から発注データを読み込み
- ASINで両シートのデータを紐付け
- 発注数を自動計算（売上/日の発注数 × 仕入情報の1商品辺り発注数）
- **発注条件：計算後の発注数が10以上のもののみ処理対象**
- **購入先URLごとに商品をグループ化（最大5商品/グループ）**
- Playwrightを使用してイーウーパスポートの注文フォームに自動入力
- 同じ購入先URLの商品は1つのフォームにまとめて入力（商品1〜5）
- タブ数を削減し、効率的な発注を実現

## 前提条件

- Python 3.8以上
- Git
- インターネット接続

## セットアップ

### 1. Python本体のインストール

このプロジェクトにはPython 3.8以上が必要です。

#### Pythonがインストールされているか確認

ターミナル（コマンドプロンプト）を開いて以下のコマンドを実行：

```bash
python3 --version
# または
python --version
```

`Python 3.8.x` 以上のバージョンが表示されればインストール済みです。次のステップに進んでください。

#### Pythonのインストール方法

**macOS の場合:**

1. **Homebrewを使う方法（推奨）**
   ```bash
   # Homebrewがインストールされていない場合
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   
   # Pythonをインストール
   brew install python3
   ```

2. **公式インストーラーを使う方法**
   - [Python公式サイト](https://www.python.org/downloads/)にアクセス
   - 「Download Python 3.x.x」ボタンをクリック
   - ダウンロードした`.pkg`ファイルを開いてインストール

**Windows の場合:**

1. [Python公式サイト](https://www.python.org/downloads/)にアクセス
2. 「Download Python 3.x.x」ボタンをクリック
3. ダウンロードした`.exe`ファイルを実行
4. **重要**: インストール時に「Add Python to PATH」にチェックを入れる
5. 「Install Now」をクリック

**Linux (Ubuntu/Debian) の場合:**

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**インストール確認:**

```bash
python3 --version
pip3 --version
```

両方のコマンドでバージョンが表示されれば成功です。

### 2. 必要なPythonパッケージのインストール

```bash
# requirements.txtから依存パッケージをインストール
pip install -r requirements.txt
```

インストールされるパッケージ：
- `gspread` - Google Sheets API クライアント
- `oauth2client` - Google API 認証
- `playwright` - ブラウザ自動化
- `python-dotenv` - 環境変数管理
- `pandas` - データ処理
- `pytest` / `pytest-mock` - テストフレームワーク

### 3. Playwrightブラウザのインストール

```bash
# Chromiumブラウザをインストール
playwright install chromium
```

このコマンドは、Playwrightが使用するChromiumブラウザをダウンロードします。

### 4. Google Sheets API認証の設定

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを作成または選択
3. Google Sheets APIを有効化
4. 認証情報 → サービスアカウントを作成
5. サービスアカウントのキー（JSON）をダウンロード
6. ダウンロードしたJSONファイルを `credentials.json` として保存
7. Googleシートでサービスアカウントのメールアドレスに閲覧権限を付与

### 5. 環境変数の設定

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

## テスト

プロジェクトにはユニットテストが含まれています。テストを実行するには：

```bash
# すべてのテストを実行
pytest

# 詳細な出力でテストを実行
pytest -v

# 特定のテストファイルを実行
pytest tests/test_sheets_reader.py

# カバレッジレポート付きでテストを実行（オプション）
pytest --cov=. --cov-report=html
```

### テストの構成

- `tests/test_sheets_reader.py`: Googleシート読み込み機能のテスト
- `tests/test_order_automation.py`: Playwright自動化機能のテスト

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

### Pythonのバージョン確認

```bash
python3 --version
# または
python --version
```

Python 3.8以上が必要です。インストールされていない場合は、[Python公式サイト](https://www.python.org/downloads/)からダウンロードしてください。

### pip コマンドが見つからない

```bash
# pipのインストール確認
pip --version

# インストールされていない場合
python3 -m ensurepip --upgrade
```

### パッケージのインストールに失敗する

```bash
# pipを最新版にアップグレード
pip install --upgrade pip

# requirements.txtから再インストール
pip install -r requirements.txt
```

### Google Sheets APIのエラー

**症状**: 「認証情報ファイルが見つかりません」

**解決方法**:
1. `credentials.json` または `service_account.json` がプロジェクトのルートディレクトリにあるか確認
2. `.env` ファイルの `GOOGLE_CREDENTIALS_FILE` のパスが正しいか確認

**症状**: 「シートにアクセスできません」

**解決方法**:
1. サービスアカウントのメールアドレスをGoogleシートの共有設定に追加
2. 閲覧権限以上を付与

### ブラウザが起動しない

**解決方法**:
```bash
# Chromiumを再インストール
playwright install chromium

# Pythonのバージョン確認（3.8以上必要）
python3 --version
```

### ログインに失敗する

**解決方法**:
1. `.env` ファイルの `YIWUPASSPORT_EMAIL` と `YIWUPASSPORT_PASSWORD` が正しいか確認
2. メールアドレスとパスワードに余計なスペースがないか確認
3. パスワードに特殊文字がある場合、正しくエスケープされているか確認

### データが紐付けられない

**解決方法**:
1. 両シートのASIN列（A列）のフォーマットが一致しているか確認
2. ASINに余計なスペースや改行が含まれていないか確認
3. 発注数や単価が数値として認識されているか確認

### 仮想環境から抜けたい

```bash
deactivate
```

### その他の問題

問題が解決しない場合は、以下を確認してください：

1. すべての依存パッケージが正しくインストールされているか
   ```bash
   pip list
   ```

2. エラーメッセージの内容を確認し、不足しているパッケージがあればインストール
   ```bash
   pip install <パッケージ名>
   ```

3. テストを実行して、基本機能が動作しているか確認
   ```bash
   pytest -v
   ```

