# 目検による動作確認手順

## 原則

- API変更の目検手順は、画面操作だけでなく、できるだけ `curl.exe`、PowerShell の `Invoke-RestMethod` / `Invoke-WebRequest`、管理コマンドなどで確認できる形にする。
- PR本文へ載せる確認コマンドは一通り実行し、成功したコマンド、レスポンス、ステータス、状態変化を本文へ反映する。
- 失敗したコマンドは未確認手順として残さず、エラー内容、原因、修正内容を整理してから本文を更新する。
- コマンド確認を省略する場合は、実行できない理由と代替確認方法を明記する。

## DB状態に依存する確認

- レビュアーが再実行しても同じ前提になるよう、原則として最初に開発・検証用DBのリセットとfixture再投入を行う手順を書く。
- 例: `python manage.py flush --no-input`、`python manage.py migrate`、`python manage.py loaddata ...`。
- 本番DBや共有DBで実行してはいけない前提を必要に応じて明記する。
- 実DBの既存ID、前回の目検で残ったデータ、手元環境だけに存在するレコードには依存しない。
- DBリセットを行わない確認が必要な場合は、リセットしない理由と、確認開始時に必要な初期データ、数量、IDの作成または確認手順を書く。

## PowerShell API確認

- セットアップ手順で得た一時変数だけに依存せず、APIレスポンスやDBから固定名・一意条件で確認対象を再取得する。
- 後続URLや更新APIに使う対象は、手順内で再取得し、古いPowerShellセッション変数に依存しない。
- JSON配列を絞り込む場合は、後続手順で使う確認対象が必ず1件のオブジェクトになる書き方にする。
- 取得したIDや確認対象は、使う前に未取得でないこと、単一IDであることを検証し、取得できない場合は明確なエラーで止める。
- `Invoke-WebRequest -SkipHttpErrorCheck` を使う場合は、`StatusCode` を確認してからレスポンス本文をJSON変換する。HTMLエラーレスポンスを `ConvertFrom-Json` に渡さない。
- 確認コマンドの出力は、レビュアーが要点を拾いやすい形にする。巨大なオブジェクトをそのまま表示せず、`[pscustomobject]`、`Select-Object`、`Format-Table` などで確認に必要な列だけを出す。
- ネストした配列やオブジェクトは、親オブジェクトの省略表示に頼らず、確認対象を別テーブルとして出力する。

### PowerShellテンプレート

```powershell
$item = (Invoke-RestMethod -Uri <list-url>).Where({ $_.<field> -eq '<fixed-name>' })[0]
if ($null -eq $item -or $item.id -is [array]) {
    throw "対象を単一IDで取得できません。id=$($item.id)"
}

$response = Invoke-WebRequest -Uri "<detail-url>/$($item.id)/" -SkipHttpErrorCheck
if ($response.StatusCode -ne 200) {
    throw "期待ステータスではありません。status=$($response.StatusCode), id=$($item.id)"
}

$detail = $response.Content | ConvertFrom-Json
[pscustomobject]@{
    status = $response.StatusCode
    id = $detail.id
    name = $detail.name
}

$detail.<nested_items> | Select-Object <columns>
```

## 貼り付けやすさ

- 長い1行の `python manage.py shell -c "..."` や複雑な引用符を含むコマンドは避ける。
- PowerShell here-string、複数行スクリプト、一時スクリプトファイルなど、貼り付けても崩れにくい形で書く。
- Django shell で複数行Pythonを実行する場合は、標準入力へ直接パイプせず、一時 `.py` を作成して `python manage.py shell -c "exec(open(r'<path>', encoding='utf-8').read())"` のように実行する。

## 取得失敗時の補足

期待した確認対象が取得できない場合は、以下を確認するようPR本文へ補足する。

- DBリセット
- fixture投入
- 目検用データ作成
- 起動中サーバーの接続DB
