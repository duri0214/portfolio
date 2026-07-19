---
name: pull-request
description: GitHub CLIでプルリクエストを作成する。「pr書いて」「PR作って」「pull request 作って」など、PR作成やPR本文作成の依頼で使用する。Issue番号をブランチ名から取得し、Issue情報・差分・テスト結果をもとに日本語のPR本文を作成して `gh pr create` まで実行する。
---

# プルリクエスト作成ルール

## 基本方針

- 出力言語とPR本文は必ず日本語にする。
- GitHub操作は原則 `gh` コマンドで行う。
- リモート上のファイル内容をAPIで直接変更しない。
- PR 作成時は、本文を表示するだけで終わらず、作成可能な状態なら `gh pr create` まで実行する。
- pull-request スキルが呼ばれた時点で未コミット変更がある場合は、`.codex/skills/commit/SKILL.md` のチェック手順を内包してコミットし、push してから PR 作成へ進む。PR 作成まで進める通常フロー上の作業なので、コミット後の push 追加確認は省略してよい。
- PR作成前に必要なローカル確認や未完了作業が残っている場合は、その理由を短く伝えて止める。push 後のリモート CI 完了待ちは行わず、CI 状態は必要に応じて取得できた時点の結果だけを報告する。

## 事前確認

1. `git status --short --branch` で現在ブランチと作業ツリーを確認する。
2. `master` / `main` 上にいる場合はPRを作成しない。
3. 未コミット変更がある場合は、`commit` スキルの手順で関連ルール確認、フォーマッター、関連テストまたは検証コマンド、コミットを実行し、そのまま現在ブランチをpushしてから次へ進む。
4. ブランチ名の先頭の数字をIssue番号として扱う。
   - 例: `740-llm-chat-rag-ddd` -> Issue `740`
5. Issue番号を取得できない場合は、マージ時にIssueを自動クローズできないためPRを作成しない。ユーザーが明示的にIssueなしで進めるよう依頼した場合だけ例外とする。
6. Issue番号が取得できる場合は `gh issue view <番号> --json title,body,labels,assignees,projectItems,url` でIssue情報を取得する。
7. `git diff --stat origin/<base>..HEAD`、`git diff --name-status origin/<base>..HEAD`、必要に応じて `git log --oneline origin/<base>..HEAD` を確認する。
8. 実行済みテストが会話やログから分かる場合はPR本文へ反映する。不明な場合は「未実施」と明記する。

## PR本文

PR本文には以下を含める。

```text
## Summary
[変更内容の要約]

- [主な変更点]

## 目検による動作確認手順
- [ ] [画面やコマンドで確認する内容]

## 自動テストでカバーできた範囲
[実行したテストコマンドと確認できた範囲]

## 関連Issue
Closes #<Issue番号>
[Issue URL]
```

- Issue番号がある場合、`## 関連Issue` には必ず `Closes #<Issue番号>` を含める。
- `gh pr create --body-file <body-file>` で作成するPR本文に `Closes #<Issue番号>` が含まれていれば、GitHubがPRをIssueの `Development` に自動リンクし、マージ時にIssueを自動クローズする。
- 別リポジトリのIssueを閉じる場合だけ `Closes owner/repo#<Issue番号>` の形式にする。
- `Closes` の代わりに `Fixes` / `Resolves` も使えるが、このスキルでは表記揺れを避けるため `Closes` に統一する。
- Issue URLだけではマージ時にIssueがOpenのまま残るため、URLのみで済ませない。

### 目検による動作確認手順の書き方

- 目検手順は、単なる操作一覧ではなく、業務上の状態変化が追えるシナリオ仕立てで順序立てて書く。
- 下準備として同時に実行できるデータ作成や管理コマンドは、読みにくくならない範囲で1つの手順にまとめてよい。
- 操作と期待値を交互に並べ、どの状態がどう変わるかを具体的な値で確認できるようにする。
- API変更の目検手順は、画面操作だけでなく、できるだけ `curl.exe`、PowerShell の `Invoke-RestMethod` / `Invoke-WebRequest`、管理コマンドなどで実行できる確認コマンドを書く。
  - PR作成前に、PR本文へ載せる確認コマンドを一通り実行し、成功したコマンドと確認できたレスポンス・ステータス・状態変化を本文へ反映する。
  - 失敗したコマンドがある場合は、PR本文に未確認の手順として残さず、コマンド、エラー内容、原因、修正内容を整理してから本文を更新する。
  - コマンド確認を省略する場合は、実行できない理由と代替確認方法を明記する。
- DB状態に依存する目検手順は、レビュアーが再実行しても同じ前提になるよう、原則として最初に開発・検証用DBのリセットとfixture再投入を行う手順を書く。
  - 例: `python manage.py flush --no-input`、`python manage.py migrate`、`python manage.py loaddata ...` など、そのリポジトリで安全に再現できるコマンドを具体的に書く。本番DBや共有DBで実行してはいけない前提も必要に応じて明記する。
  - 実DBの既存ID、前回の目検で残ったデータ、手元環境だけに存在するレコードには依存しない。
  - セットアップ手順で得た一時変数だけに依存せず、APIレスポンスやDBから固定名・一意条件で確認対象を再取得する手順を書く。別ターミナルや別セッションで実行しても確認できるようにする。
  - PowerShell で `Invoke-RestMethod` のJSON配列を絞り込む場合は、後続手順で使う確認対象が必ず1件のオブジェクトになる書き方にする。例: `$book = (Invoke-RestMethod -Uri <url>).Where({ $_.name -eq '<固定名>' })[0]`。取得と絞り込みを1行の代入パイプに詰め込むと、配列全体のIDが後続URLに展開されるなど確認が壊れることがある。
  - PowerShell で取得した対象のIDを後続URLや更新APIに使う場合は、手順内で確認対象を再取得し、古いセッション変数に依存しないようにする。実行済み確認でも `$book.id` が単一のIDになっていることと、詳細APIなど後続コマンドが `200` など期待ステータスを返すことまで確認してからPR本文に載せる。
  - PowerShell の確認コマンドで `Invoke-WebRequest -SkipHttpErrorCheck` を使う場合は、`StatusCode` を確認してからレスポンス本文をJSON変換する。`404` などHTMLエラーレスポンスのまま `ConvertFrom-Json` に渡すと、元の原因が分かりにくい二次エラーになるため、`if ($detail.StatusCode -ne 200) { throw ... }` のように明確に止める。
  - PowerShell の目検コマンドは、レビュアーがコンソールから要点を拾いやすい出力にする。巨大なオブジェクトをそのまま表示せず、`[pscustomobject]`、`Select-Object`、`Format-Table` などで `status`、対象ID、合計値、支店別数量など確認に必要な列だけを出す。
  - ネストした配列やオブジェクトを確認する場合は、親オブジェクトの省略表示に頼らず、確認対象を別テーブルとして出力する。例: `($detail.Content | ConvertFrom-Json).branch_stocks | Select-Object branch,branch_name,amount`。
  - 取得したIDや確認対象を後続手順で使う場合は、使う前に未取得でないことを検証し、未取得なら明確なエラーで止める手順を書く。空IDのまま詳細APIや更新APIへ進ませない。
  - 長い1行の `python manage.py shell -c "..."` や複雑な引用符を含むコマンドは、貼り付け時に欠けたり別コマンドと混ざりやすいため避ける。PowerShell here-string、複数行スクリプト、一時スクリプトファイルなど、貼り付けても崩れにくい形で書く。Django shell で複数行 Python を実行する場合は、標準入力へ直接パイプせず、一時 `.py` を作成して `python manage.py shell -c "exec(open(r'<path>', encoding='utf-8').read())"` のように実行する。
  - 期待した確認対象が取得できない場合に、DBリセット・fixture投入・目検用データ作成・起動中サーバーの接続DBを確認するよう補足する。
  - DBリセットを行わない確認が必要な場合は、リセットしない理由と、確認開始時に必要な初期データ・数量・IDの作成または確認手順を明記する。

例:

```text
## 目検による動作確認手順
- [ ] 下準備として、DBをリセットしてfixtureを再投入し、A支店に対象本を amount=1 で登録し、B支店にも同じ本を amount=1 で登録する。
- [ ] 対象本の詳細画面を開き、A支店 1 + B支店 1 の合計所蔵数が 2 と表示されることを確認する。
- [ ] B支店側の支店別所蔵を amount=2 に更新する。
- [ ] 対象本の詳細画面を再表示し、A支店 1 + B支店 2 の合計所蔵数が 3 に変わることを確認する。
```

## PR作成

1. baseブランチは通常 `master` とする。リポジトリの既定ブランチが明らかに異なる場合だけ、その既定ブランチを使う。
2. PRタイトルはIssueタイトルをベースにする。
   - 推奨: `#<Issue番号> <Issueタイトル>`
3. PR作成前に本文を確認し、Issue番号があるのに `Closes #<Issue番号>` または `Closes owner/repo#<Issue番号>` が含まれていない場合は本文を修正してから進める。
4. PR本文は一時ファイルに書き出し、`gh pr create --base <base> --head <current-branch> --title "<title>" --body-file <body-file>` で作成する。
5. 作成後に `gh pr view --json url,number,title` でURLを確認する。

## メタ情報設定

PR作成後、設定できるものを `gh` で設定する。失敗してもPR作成自体は維持し、失敗内容だけ伝える。

- Assignee: `gh api user --jq .login` で取得した自分自身を設定する。
- Label: Issueに付いているlabelをPRにも設定する。Issueにlabelがなくても、差分が `.codex/rules/` または `.codex/skills/` 配下を主対象にしており、既存の `rules-skills` ラベルがある場合は、対応 Issue とPRの両方に設定する。
- Project: IssueのProject情報を確認し、対応するProjectへPRを追加する。
  - Issueの `projectItems` にProjectが1件だけある場合は、そのProjectを使う。
  - Issueの `projectItems` にProjectが複数ある場合は、どのProjectへPRを追加するかユーザーへ確認する。
  - Issueの `projectItems` にProjectがない場合は、`gh project list --owner <owner> --format json` でProject一覧を確認する。取得できたProjectが1件だけならそのProjectを使い、複数ある場合はユーザーへ確認する。
  - Projectが決まったら、PR作成後に `gh pr edit <PR番号> --add-project "<Project名>"` を実行する。
  - `gh pr view <PR番号> --json projectItems` でProject追加を確認する。Projectが空のままなら、`gh project item-add <Project番号> --owner <owner> --url <PR URL>` でPR URLを直接追加する。
  - Projectへ直接追加した場合は、必要に応じて `gh project item-edit --project-id <Project ID> --id <Item ID> --field-id <Status field ID> --single-select-option-id <Status option ID>` でIssueと同じStatusへ更新する。
  - Project追加後は、必ず `gh pr view <PR番号> --json projectItems` でProject名とStatusが入っていることを確認する。
  - 権限不足の場合は `gh auth refresh -s read:project -s project` が必要なことを伝える。

## 本文だけ求められた場合

ユーザーが明示的に「本文だけ」「PR文だけ」と依頼した場合は、PR作成は行わず本文だけ返す。

