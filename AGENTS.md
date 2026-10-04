# Codex Project Instructions

このリポジトリで作業するときは、作業内容に関係する `.codex/rules/` と `.codex/skills/` を確認する。

## Rules

- 常時適用する運用ルールは `.codex/rules/` に配置する。
- Python・Django・テストなど、作業内容に関係するルールを着手前に確認する。
- `master` へ直接コミットせず、Issue に対応するトピックブランチで作業する。
- 新規またはまっさらなスレッドにこのリポジトリの GitHub Issue URL が貼られた場合は、その Issue を対応対象として扱い、追加確認なしで内容確認、ブランチ作成、Project の `In progress` 更新、作業着手まで進める。
- コード、ルール、ドキュメントを変更する依頼では、確認後に commit、push、PR作成または更新まで進める。ユーザーが `commit不要`、`push不要`、`PR不要`、`まだコミットしない` と明示した場合だけ停止する。
- 説明、調査、レビュー結果の報告、状態確認だけを求められた場合は、変更や commit、push、PR作成を行わない。
- 説明や処理を追加・変更するときは、MECE（漏れなく重複なく）を意識して整理する。

## Skills

- Codex 用スキルは `.codex/skills/<skill-name>/SKILL.md` に配置する。
- スキル名とフォルダ名は小文字・数字・ハイフンを使う。
- ユーザー依頼がスキルの `description` に該当する場合は、該当 `SKILL.md` を読んでから作業する。
- 個別手順として残すスキルは `ticket`、`review`、`cleanup-branch` とする。

## Classification

- rules と skills は役割で分ける。同じ対象に関する項目でも、常時適用の制約は rules、特定依頼で起動する手順は skills に置く。
- rules/skills を整備する場合は、今回変更する各ファイルの役割が重複していないか確認する。通常のソースコード変更全体にはこの観点を広げない。
- `references/` は分岐別の補助資料や追加資料が必要な場合だけ使い、本文の単純な退避先として使わない。
- Rules: `centos-to-ubuntu-setup`, `django`, `portfolio`, `principles`, `python`, `testing`
- Skills: `cleanup-branch`, `review`, `ticket`

## 常用フロー

### ブランチ作成

1. 作業開始前に対応する GitHub Issue を用意する。新規スレッドに Issue URL が貼られている場合は、その Issue を使い、追加確認なしで着手する。Issue がなければ `ticket` スキルで作成する。
2. `git status --short --branch` で現在のブランチと変更を確認する。
3. 未コミット変更がある場合は `git stash push -u -m "branch:<Issue番号>"` で退避する。既存作業を壊す可能性がある変更は、復元先を判断するまで stash に残す。
4. `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name` で既定ブランチを確認し、`git fetch origin --prune` で最新化する。
5. 既定ブランチを起点に、`<Issue番号>-<英小文字と数字の短い説明>` 形式のトピックブランチを作成する。例: `955-integrate-codex-hotl`。
6. Issue の assignee、Project、Project status を確認する。未設定なら `gh issue edit <Issue番号> --add-assignee <login> --add-project <Project名>` などで設定する。着手後の Project status は `gh project item-edit <Project番号> --owner <owner> --url <Issue URL> --field Status --value "In progress"` で更新する。`gh issue view <Issue番号> --json assignees,projectItems` で反映を再確認する。

### コミットと push

1. `master` / `main` 上ではコミットしない。Issue 番号付きのトピックブランチを使う。
2. `AGENTS.md` と変更に関係する `.codex/rules/` を確認する。
3. Python変更では、対象ファイルに `black` を実行し、変更範囲に応じたDjangoテストを実行する。ルール・ドキュメントだけの変更では `git diff --check` を実行する。
4. `git diff --stat`、`git diff --check`、`git diff` でIssueに関係する差分だけであることを確認する。
5. 問題がなければ、内容が分かる短いメッセージでコミットし、push する。変更依頼では、明示的な停止指定がない限り確認待ちで止めない。
6. `git commit --amend`、`git push --force`、`git push --force-with-lease` は、明示的な許可なしに使わない。

### PR作成と更新

1. `master` / `main` 上ではPRを作成しない。baseブランチは `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name` で確認する。
2. ブランチ名の先頭の数字をIssue番号として扱い、Issueのタイトル、本文、ラベル、assignee、Projectを確認する。
3. `git diff --stat origin/<base>..HEAD`、`git diff --name-status origin/<base>..HEAD` でPRの差分を確認する。
4. PR本文は日本語で、概要、主な変更点、目検手順、自動テストの範囲、`Closes #<Issue番号>` を含める。
5. 目検手順は操作と期待値を `- [ ]` 形式で書く。ユーザーが提示した画面や操作結果で期待値を確認できた項目は、確認した証跡と範囲をPR本文に記して `[x]` に更新する。未確認の操作や期待値が同じ項目に含まれる場合はチェック欄を分割し、未確認分を `[ ]` に残す。実行・確認していない項目を `[x]` にしない。
6. 現在のブランチにPRがなければ `gh pr create --base <base> --head <current-branch> --title "#<Issue番号> <Issueタイトル>" --body-file <body-file>` で作成する。既存PRがあれば `gh pr edit <番号> --body-file <body-file>` で更新する。
7. 作成・更新後に `gh issue view <Issue番号> --json assignees,labels,projectItems` と `gh pr view <PR番号> --json url,assignees,labels,projectItems` を実行し、IssueとPRのassignee、ラベル、Project名、Project statusを照合する。PR側に不足があれば `gh pr edit <PR番号> --add-assignee <login> --add-label <ラベル名> --add-project <Project名>` などで補う。Project statusは `gh project item-edit <Project番号> --owner <owner> --url <PR URL> --field Status --value <Issueのstatus>` で揃える。両方を再取得して反映を確認し、失敗した項目は原因と現在の値を報告する。変更依頼では、明示的な `PR不要` 指定がない限り作成または更新まで進める。

git や gh の操作が失敗した場合は、API で迂回せず原因を切り分けて報告する。Project操作の権限が不足する場合は、`gh auth refresh -s read:project -s project` が必要であることを伝える。

## Apacheアクセス集計メールの運用（Issue #954）

この機能を本番で有効化するときは、実装確認とサーバー運用確認を分け、次の順序を守る。詳細なコマンドは [`docs/apache_access_report.md`](docs/apache_access_report.md) に集約する。

1. この処理は `lib/apache_access` に置き、Djangoアプリ、モデル、migrationを追加しない。`home` はコンテンツカタログの責務だけを持つ。
2. サーバー管理者が Apache の `LogFormat` / `CustomLog`、VirtualHost ごとの出力先、リバースプロキシ経由の送信元、ローテーション形式を確認する。combined 形式でない場合や対象ログが特定できない場合は登録を進めない。
3. サーバーの `.env` に `APACHE_ACCESS_LOG_GLOBS`、`APACHE_ACCESS_REPORT_PATH`、固定宛先の `APACHE_REPORT_RECIPIENT`、`MAIL_SMTP_*`、`MAIL_USE_TLS` を設定し、`.env` を Git やログへ出さない。
4. 定期処理ユーザーだけに現行・ローテート済み Apache アクセスログの読み取り権限を付与し、`www-data` が読めないことを確認する。匿名化済み JSON の保存先だけは `ubuntu` と `www-data` の双方が読み書きできるようにする。
5. `sudo -u ubuntu -H bash -lc 'cd /var/www/html/portfolio && .venv/bin/python -m lib.apache_access.report_service'` を手動で一度実行し、成功を確認してから `ubuntu` の crontab に1時間ごとの定期実行を1行だけ登録する。この機能に `manage.py migrate` は不要。
6. スーパーユーザーがブラウザで「アクセス集計をメール送信」を押し、固定宛先への到着と対象期間・生成時刻・件数を確認する。未ログイン・一般ユーザーの送信、未設定・古い集計・SMTP失敗の表示も確認する。
