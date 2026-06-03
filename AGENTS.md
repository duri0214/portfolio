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

- rules と skills は役割で分ける。同じ対象に関する項目でも、常時適用の制約は rules、特定依頼で起動する手順は skills に置く。
- rules/skills を整備する場合は、今回変更する各ファイルの役割が重複していないか確認する。通常のソースコード変更全体にはこの観点を広げない。
- `references/` は分岐別の補助資料や追加資料が必要な場合だけ使い、本文の単純な退避先として使わない。
- Rules: `centos-to-ubuntu-setup`, `django`, `kiss`, `portfolio`, `python`, `testing`
- Skills: `branch`, `commit`, `pull-request`, `ticket`
