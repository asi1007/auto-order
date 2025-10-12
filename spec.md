Googleシートから発注に必要な情報を読み込み, EUパスポートのウェブページから発注を自動で行うシステム

# 発注に必要な情報
## 発注数の情報
- シートのURL: https://docs.google.com/spreadsheets/d/1aAliE0u45YbMwcBMczrLrG82MRMjOVc999L3GWCUENE/edit?gid=1783029617#gid=1783029617
- シート名:  売上/日
- ASINの列: A
- 発注数の列: 2


## 発注先に関係する情報 
- シートのURL: https://docs.google.com/spreadsheets/d/1aAliE0u45YbMwcBMczrLrG82MRMjOVc999L3GWCUENE/edit?gid=2001083245#gid=2001083245
-　シート名:  仕入情報
- ASINの列:  A
- 題名: E列
- 購入先URL: D列
- 色・サイズ等指定: F列
- 1商品辺り発注数:  G列
- 単価:  L列
紐づけはASINで実施


# イーウーパスポートのウェブページ
読み込んだ各ASINに対して、新しくタブを開き下記URLをh楽、各種情報を入力する
- URL: https://yiwupassport.jp/order
- 商品名、商品URL、色サイズ等指定、発注数、単価を入力
- 発注数は「売上/日」の発注数 × 「仕入情報」
- 注文確認ボタンはまだクリックしない。

# 使用する技術スタック
- python
- playwrihgt
