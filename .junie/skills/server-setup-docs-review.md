# Server Setup Docs Review Skill

## 概要
Ubuntu + Apache (mod_wsgi) + Django 環境において、セットアップ手順や権限設定が正しく記載されているかをレビューするための基準を定義します。
Junie はサーバーに対して直接コマンドを実行することはできませんが、`README.md` や `docs/qiita/` などのドキュメントを編集・レビューする際に、過去のトラブル（PermissionError 等）を繰り返さないための「チェックリスト」として活用します。

## レビューの観点

### 1. 所有権と基本権限の記述
- [ ] 所有者が `ubuntu:www-data` になっているか？（`www-data:www-data` だと `ubuntu` で `git clean` やバッチが失敗する）
- [ ] ディレクトリに `775`、ファイルに `664` が設定されているか？（グループ＝お互いに書き込み可能か）

### 2. ACL (Access Control List) の記述
- [ ] `setfacl` コマンドが含まれているか？（`chmod` だけでは新規ファイルに権限が継承されないため必須）
- [ ] `media/` などの書き込みが発生するディレクトリに対して設定されているか？

### 3. Apache (mod_wsgi) 設定の記述
- [ ] `Alias /media/` と `Alias /static/` の両方が設定されているか？（`DEBUG=False` で画像が出ない原因の多くはこれ）
- [ ] `<Directory>` ブロックで `Require all granted` が記述されているか？

### 4. Django (settings.py) 設定の記述
- [ ] `FILE_UPLOAD_PERMISSIONS = 0o664` が設定されているか？
- [ ] `FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o775` が設定されているか？

## トラブル事例と対策（ナレッジ）
- **事例**: `DEBUG=False` にした瞬間にチャート画像が Not Found になった。
  - **原因**: Apache の `Alias /media/` 設定が漏れていた。
  - **対策**: `000-default.conf` 等に `Alias /media/` を追記する手順をドキュメントに含める。
- **事例**: バッチ実行時に `PermissionError` でファイルが消せなかった。
  - **原因**: Apache (`www-data`) が作ったファイルにグループ書き込み権限がなかった。
  - **対策**: `settings.py` でパーミッションを明示し、かつ OS 側で `setfacl` を設定する手順を推奨する。
