# VIDEO CUE の成果物受信と閲覧

`video_cue` は engine の `analysis.json` と連結済みハイライト MP4 を受け取り、
`MEDIA_ROOT/video_cue/<動画ID>/` に保存します。元動画とイベント別クリップは受け取りません。
スタッフは `/video_cue/` から保存済みの結果を一覧・再生できます。

## engine #7 と Django #980 の転送契約

- `POST /video_cue/api/results/<動画ID>/`。動画 ID は英数字、ハイフン、アンダースコアのみ。
- `Authorization: Bearer <VIDEO_CUE_UPLOAD_TOKEN>` を必須とします。トークンは双方の環境変数に設定し、JSON、URL、ログには含めません。未設定の Django はすべての送信を401で拒否します。
- `multipart/form-data` のファイル項目は `analysis`（UTF-8 JSON、最大8 MiB）と `highlight`（MP4、最大128 MiB）です。同名項目の複数送信や他の項目は拒否します。
- JSON は engine の schema 2、`input.path`、`input.duration_seconds`、`events`、`highlight_path`、イベント時刻と `highlight_start_seconds` を使います。イベントが1件以上なら `highlight_path` は `highlights.mp4` で、`highlight` が必要です。イベント0件では `events: []`、`highlight_path: null` とし、`highlight` は送信しません。
- `input.path` は元動画名だけを表示用に保存します。`clip_path` は保存時に `null` にします。長尺の元動画、個別クリップ、元動画の絶対パスは共有・配信しません。
- 成功時は新規登録が `201 {"key":"0001","created":true}`、同じ内容の再送が `200 {"key":"0001","created":false}` です。同じ ID に異なる内容を再送すると409で、既存の正常な成果物を保持します。更新する場合は新しい動画 ID を使用します。
- 認証失敗は401、multipart 以外は415、不正な項目・JSON・MP4・イベント0件の矛盾は422、容量超過は413、保存不能は503です。失敗は `{"error":"..."}` を返し、engine はローカル成果物を残して再送できます。
- engine 側の接続・応答待ちタイムアウトは120秒を目安に設定します。Webサーバー／リバースプロキシの本文上限は multipart の余白を含め138 MiB以上、タイムアウトは120秒以上にしてください。Django は `Content-Length` とファイル実体の双方で容量を検査します。

受信は一時ディレクトリで検証を終えてから動画 ID のディレクトリへ公開します。
保存途中で失敗した一時ファイルは削除され、一覧には出ません。
API は CSRF 免除で Bearer トークンを検証します。HTTPS 経由で送信し、
`/media/video_cue/` を Web サーバーから直接公開しないでください。再生はスタッフ権限付きの
`/video_cue/<動画ID>/media/highlight/` を使います。

## 目検手順（上から順に実施）

この手順は Django と engine #7 の送信機能が使える環境で実施します。engine #7 が未実装の場合は、自動テストまでを実施し、engine 送信以降を未実施として PR に記録します。

### 事前準備

1. `.env` に `VIDEO_CUE_UPLOAD_TOKEN` を設定し、engine 側にも同じ値を設定する。開発環境の例は `dev1234`。
2. スタッフアカウントを用意する。未作成なら別の PowerShell で `.venv\Scripts\python.exe manage.py createsuperuser` を実行する。
3. Django を起動する。

```powershell
Set-Location C:\Users\yoshi\OneDrive\dev\portfolio
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

4. ブラウザーで `http://127.0.0.1:8000/accounts/login/?next=/video_cue/` を開き、スタッフでログインする。
5. engine のイベントあり結果から、`analysis.json` と同じフォルダーの `highlights.mp4` の絶対パスを確認する。

### 1. 正常送信と表示

engine の送信機能を使うか、次の PowerShell で API に送信する。`$analysisPath` と `$highlightPath` は実際の結果に置き換える。

```powershell
$env:VIDEO_CUE_UPLOAD_TOKEN = 'dev1234'
$analysisPath = 'C:\path\to\0001\analysis.json'
$highlightPath = 'C:\path\to\0001\highlights.mp4'
curl.exe -i -X POST 'http://127.0.0.1:8000/video_cue/api/results/0001/' `
  -H "Authorization: Bearer $env:VIDEO_CUE_UPLOAD_TOKEN" `
  -F "analysis=@$analysisPath;type=application/json" `
  -F "highlight=@$highlightPath;type=video/mp4"
```

期待値は HTTP 201 と `created: true`。ログイン済みブラウザーで `/video_cue/` を再読み込みし、`録画 0001` を開く。
ハイライトが表示され、イベント一覧、タイムライン、「前」「再生」「次」で頭出しできることを確認する。
元動画・個別クリップの切替ボタンが表示されないことも確認する。

### 2. 同じ内容の再送

同じコマンドをもう一度実行する。期待値は HTTP 200 と `created: false`。一覧に重複が増えず、既存のハイライトを再生できることを確認する。

### 3. 異なる内容の重複送信

`analysis.json` のイベント時刻または変化量を有効な範囲で変更したコピーを作り、同じ動画 ID `0001` に送信する。
期待値は HTTP 409。元の `0001` の JSON とハイライトが変更されていないことを確認する。

### 4. イベント0件

engine のイベント0件の結果（`events: []`、`highlight_path: null`）を `analysis` だけで `0002` に送信する。
期待値は HTTP 201。`録画 0002` を開き、「イベント0件」と「再生するハイライトはありません」が表示されることを確認する。

### 5. 認証と権限

1. 正常な送信コマンドの Bearer 値を `wrong` に変える。期待値は HTTP 401。
2. ブラウザーからログアウトするかシークレットウィンドウで `/video_cue/` を開く。期待値は HTTP 403 とログイン案内。

### 6. 狭い画面幅

ブラウザー幅を390px程度にして `0001` を開き、プレイヤー、前・再生・次、イベント一覧を横スクロールなしで操作できることを確認する。

一覧は `MEDIA_ROOT/video_cue/` の完成済み成果物だけを参照します。
外部フォルダーを指定する設定はありません。元動画と個別クリップの再生経路もありません。
画面の「録画内の時刻」は JSON のイベント時刻から計算し、元動画ファイルにはアクセスしません。
未完了結果には409、不正JSONには422を返します。ハイライト動画が欠損した場合は
説明を表示し、再生操作を無効にします。

自動テスト:

```powershell
.venv\Scripts\python.exe manage.py test video_cue --noinput
node --test video_cue/tests/playback.test.mjs
```
