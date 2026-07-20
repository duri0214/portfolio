---
name: pull-request
description: GitHub CLIでプルリクエストを作成する。「pr書いて」「PR作って」「pull request 作って」など、PR作成やPR本文作成の依頼で使用する。Issue番号をブランチ名から取得し、Issue情報・差分・テスト結果をもとに日本語のPR本文を作成して `gh pr create` まで実行する。
---

# プルリクエスト作成ルール

## 基本方針

- 出力言語とPR本文は必ず日本語にする。
- GitHub操作は原則 `gh` コマンドで行う。
- リモート上のファイル内容をAPIで直接変更しない。
- PR作成可能な状態なら、本文提示だけで止めず `gh pr create` まで実行する。
- 未コミット変更がある場合は `commit` スキルの手順を内包し、確認、コミット、push を済ませてからPR作成へ進む。
- PR作成前に未完了作業や確認不能な事項が残る場合は、理由を短く伝えて止める。push後のリモートCI完了待ちは不要。

## 事前確認

1. `git status --short --branch` で現在ブランチと作業ツリーを確認する。
2. `master` / `main` 上にいる場合はPRを作成しない。
3. 未コミット変更がある場合は、`commit` スキルに従って関連ルール確認、フォーマッター、関連テストまたは検証、コミット、push を行う。
4. ブランチ名の先頭の数字をIssue番号として扱う。例: `740-llm-chat-rag-ddd` -> Issue `740`。
5. Issue番号を取得できない場合は、ユーザーが明示的にIssueなしで進めるよう依頼した場合だけ続行する。
6. Issue番号がある場合は `gh issue view <番号> --json title,body,labels,assignees,projectItems,url` でIssue情報を取得する。
7. `git diff --stat origin/<base>..HEAD`、`git diff --name-status origin/<base>..HEAD`、必要に応じて `git log --oneline origin/<base>..HEAD` を確認する。
8. 実行済みテストが分かる場合はPR本文へ反映する。不明な場合は「未実施」と明記する。

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
- 別リポジトリのIssueを閉じる場合だけ `Closes owner/repo#<Issue番号>` の形式にする。
- Issue URLだけではマージ時にIssueがOpenのまま残るため、URLのみで済ませない。

## 目検手順

- 目検手順は、業務上の状態変化が追えるシナリオ仕立てで順序立てて書く。
- 操作と期待値を交互に並べ、どの状態がどう変わるかを具体的な値で確認できるようにする。
- API変更やDB状態に依存する確認を書く場合は、必ず [references/manual-check.md](references/manual-check.md) を読んでからPR本文を作成・更新する。

## PR作成

1. baseブランチは通常 `master` とする。既定ブランチが明らかに異なる場合だけ、その既定ブランチを使う。
2. PRタイトルはIssueタイトルをベースにする。推奨: `#<Issue番号> <Issueタイトル>`。
3. PR本文を確認し、Issue番号があるのに `Closes #<Issue番号>` または `Closes owner/repo#<Issue番号>` がない場合は修正する。
4. PR本文を一時ファイルに書き出し、`gh pr create --base <base> --head <current-branch> --title "<title>" --body-file <body-file>` で作成する。
5. 作成後に `gh pr view --json url,number,title` でURLを確認する。

## メタ情報設定

PR作成後、設定できるものを `gh` で設定する。失敗してもPR作成自体は維持し、失敗内容だけ伝える。

- Assignee: `gh api user --jq .login` で取得した自分自身を設定する。
- Label: Issueに付いているlabelをPRにも設定する。
- Project: IssueのProject情報を確認し、対応するProjectへPRを追加する。権限不足の場合は `gh auth refresh -s read:project -s project` が必要なことを伝える。

## 本文だけ求められた場合

ユーザーが明示的に「本文だけ」「PR文だけ」と依頼した場合は、PR作成は行わず本文だけ返す。
