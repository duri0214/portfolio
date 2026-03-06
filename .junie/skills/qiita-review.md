# Qiita Review Skill

## 概要
`docs/qiita/centos_to_ubuntu_setup.md`（CentOSからUbuntuへの移行手順）が、最新の本番環境のベストプラクティスに基づいているかをレビューするための基準を定義します。
Junie はサーバーを直接操作できませんが、ドキュメント内のコマンドや設定値が正しいかをチェックし、ユーザーに提案することで、本番環境での PermissionError や表示トラブルを未然に防ぎます。

## レビューの観点 (チェックリスト)

### 1. 権限管理 (Ownership & Permissions)
- [ ] **所有者**: `sudo chown -R ubuntu:www-data /var/www/html/portfolio` が推奨されているか？
  - `www-data:www-data` だと `ubuntu` ユーザーでの `git clean` やバッチ実行が失敗するためNG。
- [ ] **基本権限**: ディレクトリに `775`、ファイルに `664` を付与する手順（`find ... -exec chmod ...`）が含まれているか？
  - グループ（`ubuntu` と `www-data` 両方が所属）に書き込み権限を与える必要がある。
- [ ] **ACL (Access Control List)**: `setfacl` コマンドによる権限継承の設定が含まれているか？
  - `chmod` だけでは新規ファイルに権限が引き継がれないため、`media/` 等の動的ディレクトリには必須。
  - 例: `sudo setfacl -R -d -m g:www-data:rwx /var/www/html/portfolio/media`

### 2. Apache (VirtualHost) 設定
- [ ] **Alias /media/**: `Alias /media/ /var/www/html/portfolio/media/` が設定されているか？
  - `DEBUG=False` 時、これがないとバッチ生成された画像（チャート等）が Not Found になる。
- [ ] **Alias /static/**: `Alias /static/ /var/www/html/portfolio/static/` が設定されているか？
- [ ] **Directory権限**: 各 Alias に対して `<Directory>` ブロックで `Require all granted` が設定されているか？

### 3. Markdown 構造 (Heading Levels)
- [ ] **見出しの階層**: `#` の数が飛んでいる（例: `##` の次に直接 `####` が来る）箇所がないか？
  - 段落がガタガタになっている（例: `hoge-error` のようにレベルが不自然に飛んでいる）場合は、正しい順序（`##` -> `###` -> `####`）に修正してください。
  - **重要**: 本当にその構成を意図している場合もあるため、**必ず修正案を UI で提示し、ユーザーに確認を取ってから適用**してください。
  - 段落が 2 個飛ばされているようなケースは、多くの場合ミス（提案通りで OK）である可能性が高いです。

### 4. トラブル事例とナレッジ
- **事例**: バッチ実行で `os.remove()` が `PermissionError` になる。
  - **解決**: ファイルを `ubuntu:www-data` 所有にし、かつ `664` 権限を維持する（ACL/settings.pyの設定）。
- **事例**: 画像が 404 Not Found になる（ファイルは存在する）。
  - **解決**: Apache の `Alias /media/` 設定漏れを確認する。
- **事例**: 見出しのレベルが不自然に飛んでいる（例: `##` の直後に `####`）。
  - **解決**: 段落構造を整理し、UI でユーザーに確認を取る。

## 運用
`commit-and-pr.md` のステップ 1 に基づき、PR作成前に必ずこの基準で `docs/qiita/` および `README.md` をレビューしてください。
