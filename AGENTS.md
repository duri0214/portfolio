# Codex Project Instructions

このリポジトリで作業するときは、必要に応じて `.codex` 配下のルールとスキルを参照する。

## Rules

- 常時適用する運用ルールは `.codex/rules/` に配置する。
- Python・Django・テストなど、作業内容に関係するルールを着手前に確認する。
- `master` へ直接コミットせず、Issue に対応するトピックブランチで作業する。

## Skills

- Codex 用スキルは `.codex/skills/<skill-name>/SKILL.md` に配置する。
- スキル名とフォルダ名は小文字・数字・ハイフンを使う。
- ユーザー依頼がスキルの `description` に該当する場合は、該当 `SKILL.md` を読んでから作業する。

## Classification

- 同じ項目を rules と skills の両方に置かない。
- `references/` は分岐別の補助資料や追加資料が必要な場合だけ使い、本文の単純な退避先として使わない。
- Rules: `centos-to-ubuntu-setup`, `django`, `portfolio`, `python`, `testing`
- Skills: `branch`, `issue`, `kiss`, `pull-request`
