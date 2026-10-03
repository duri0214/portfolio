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

## 起動と確認

`.env` に `VIDEO_CUE_UPLOAD_TOKEN` を設定し、engine に同じ値と送信先 URL を設定します。
管理者はトークンを安全なランダム文字列として発行してください。ブラウザーで
`/video_cue/` を開くスタッフアカウント（`is_staff=True`）を用意します。

1. engine でイベントを含む動画を解析し、送信を有効化する。201が返り、一覧に動画 ID が現れる。
2. 詳細でハイライトを再生し、前／再生／次、一覧、タイムラインからイベントに移動できることを確認する。
3. 同じ成果物を再送して200、内容を変えて同じ ID に送って409を確認する。元の結果は再生できる。
4. イベント0件を送信し、動画なしの結果と「イベント0件」の説明が表示されることを確認する。
5. トークンを誤らせて401を確認する。スタッフ以外の閲覧は403となる。

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
