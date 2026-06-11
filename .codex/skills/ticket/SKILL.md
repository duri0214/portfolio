---
name: ticket
description: GitHub Issue を日本語で整理・作成する。「issue書いて」「チケット作って」「リファクタリングチケット作って」「ticket作って」など、開発着手前の課題整理や GitHub Issue 作成の依頼で使用する。
---

# チケット・Issue 作成規約

- **出力言語は必ず日本語とすること。**
- 会話の流れと調査結果から、GitHub Issue に起票できる作業内容を整理する。
- ユーザーから「issue書いて」「チケット作って」などの依頼があった場合は、`gh issue create` で GitHub Issue を作成する。
- ユーザーから明示的に「本文だけ」「下書きだけ」と依頼された場合のみ、Markdown のコードブロック（生md）で Issue 本文を生成する。
- GitHub Issue を作成する直前に、親チケットがあるか確認する。親チケットがある場合は Issue 番号を指定してもらう。

## Issue 本文の生成フォーマット

```markdown
**タイトル:** [タイトル]

**本文:**
## 概要
[概要]

## 主な対応内容
- [対応内容]

## 期待される効果
- [効果]
```

## 報告

- Issue 本文だけを生成した場合は、本文だけ生成したことを簡潔に報告する。
- GitHub Issue を作成した場合は、作成した Issue のURLと要約を報告する。
- 親チケットを指定された場合は、親子関係を設定できたか報告する。
- Issue 作成後にブランチを作る場合は、`branch` スキルへ引き継ぐ。

## Issue 作成時のメタ情報設定

GitHub Issue を実際に作成する場合は、本文生成に加えて以下をできるだけ設定すること。設定できない項目があっても、Issue 作成自体は止めないこと。

- **Parent issue**: Issue 作成直前に「親チケットがある場合は Issue 番号を指定してください」と確認する。ユーザーが親 Issue 番号を指定した場合は、本文に `親チケット: #<番号>` を含め、Issue 作成後に GitHub の Sub-issues 機能で親子関係を設定する。設定できない場合は、本文上の参照だけは残し、失敗理由を報告する。
- **Assignee**: `gh api user --jq .login` などで自分自身の GitHub ユーザー名を取得し、Issue の assignee に自分自身を設定する。
- **Label**: 依頼内容や対象アプリから適切な label を推測できる場合は設定する。判断できない場合は省略する。
- **Projects**: `gh project list --owner duri0214 --format json` などで Project 一覧を取得し、取得できた Project が1件だけなら、その Project の `title` を使って Issue に設定する。Project 名を固定文字列で決め打ちしないこと。Project 操作の権限が不足している場合は、`gh auth refresh -s read:project -s project` が必要なことを伝える。
