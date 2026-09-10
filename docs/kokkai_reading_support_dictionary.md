# 国会会議録の読み仮名支援辞書

会議録の読み仮名支援辞書は、`kokkai` アプリの `ReadingSupportEntry` で管理します。辞書項目を削除すると、会議録の表示にも使われなくなります。

## KOKKAI内の管理画面

KOKKAIの会議録一覧にある「読み仮名支援辞書」から管理画面に入ります。管理者は辞書ビューア、手動登録、CSV取り込みを利用できます。

- 「辞書ビューア」: 登録済み項目の確認・編集・削除
- 「辞書項目を追加」: 辞書項目の手動登録
- 「CSVから取り込む」: 確認済みの辞書項目を一括登録

元資料をGPTでCSV形式に整え、内容を確認してから「CSVから取り込む」で登録します。

## CSV形式

ファイルはUTF-8のカンマ区切りで、次の列を使用します。

```csv
surface,reading,description,source_url
NISA,ニーサ,少額投資非課税制度,https://example.com/nisa
お諮り,おはかり,,
```

`surface` と `reading` は必須です。`description` がある項目は説明付きの辞書項目として扱い、`source_url` も必須です。`description` が空の項目は読み仮名だけを補正する項目として扱います。

同じ正規化表記がCSV内に複数ある場合や、必須項目・URL形式が不正な場合は、CSV全体を保存しません。既存項目の内容を変更する場合だけ「既存データを更新する」を選択します。

## コマンドによる取り込み

```powershell
.venv\Scripts\python.exe manage.py import_reading_support path\to\dictionary.csv
```

既存項目を更新する場合は `--update-existing` を付けます。

```powershell
.venv\Scripts\python.exe manage.py import_reading_support path\to\dictionary.csv --update-existing
```
