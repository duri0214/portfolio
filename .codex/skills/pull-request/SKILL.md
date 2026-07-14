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
- CI確認が必要など、PR作成前に必要な作業が残っている場合は、その理由を短く伝えて止める。

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

