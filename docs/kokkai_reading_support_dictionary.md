# 国会会議録の読み仮名支援辞書

会議録の読み仮名・用語解説は `kokkai` アプリの `ReadingSupportEntry` で管理します。辞書の `is_active` が無効のエントリは本文解析に使われません。

## KOKKAI内の管理画面

KOKKAIの会議録一覧にある管理機能ボタンから、管理者でログインして次の画面を使います。

- 「辞書を管理」: 用語と読み補正の追加・編集・無効化
- 「CSV取り込み」: 確定済みCSVの一括登録
- 「候補下書き」: Web情報から作成したGPT候補の確認・修正・承認
- 「Web情報から候補を作成」: URLまたは本文からGPT候補を作成

GPT候補は作成した時点では本文表示へ反映されません。候補の表記、読み、説明、カテゴリ、出典URLを確認・修正し、候補の「登録承認」を選択してから下書き詳細の「承認済み候補を辞書へ登録」を実行します。読みや説明を確定できない候補は、確認メモを残したまま承認しないでください。

## CSV形式

ファイルはUTF-8のカンマ区切りで、次の列を使用します。

```csv
surface,reading,description,category,source_url,entry_type,is_active
FOIP,フォイップ,Free and Open Indo-Pacific（自由で開かれたインド太平洋）の略称です。,政策・略語,https://www.meti.go.jp/policy/external_economy/trade/foip/index.html,term,true
お諮り,おはかり,,,,reading_override,true
```

`surface` と `reading` は必須です。`entry_type` は `term` または `reading_override` を指定できます。省略した場合、`description`、`category`、`source_url` がすべて空なら読み補正、それ以外は用語として扱います。

用語は `description` と `source_url` も必須です。`category` は任意ですが、読み補正では3列すべてを空にできます。`is_active` を省略すると有効になり、`false` を指定すると無効で登録されます。

同じ正規化表記（全角・半角、大小文字、空白を統一した表記）がCSV内に複数ある場合や、必須項目・URL形式が不正な場合は、行番号と理由を表示して全体を保存しません。

## コマンドによる取り込み

KOKKAI内の画面を使わずに、次のコマンドでも取り込めます。

```powershell
.venv\Scripts\python.exe manage.py import_reading_support path\to\dictionary.csv
```

同じ内容のCSVを再度取り込むとスキップされます。既存データの内容を変更するCSVを反映する場合だけ、明示的に更新オプションを付けます。

```powershell
.venv\Scripts\python.exe manage.py import_reading_support path\to\dictionary.csv --update-existing
```

エラーがある場合は行番号と理由を標準エラー出力へ表示し、保存せず終了します。

## Web情報からの候補作成

「辞書候補下書き」の「Web情報から候補を作成」で、公式ページのURLまたは本文を入力します。URLを指定した場合はページ本文を取得し、`OPENAI_API_KEY` で設定したGPTへ候補作成を依頼します。GPTの出力には用語、読み、説明、カテゴリ、出典URLの候補が含まれます。

APIキーが未設定、取得した本文が空、またはGPTの出力形式が不正な場合は下書きを作成しません。GPTの候補を公開辞書へ直接登録する処理はなく、管理者の承認操作を経て登録します。
