---
apply: always
---

# ポートフォリオ共通業務ルール (Portfolio Common Rules)

## Git/GitHub 操作
- GitHub API、GitHub Contents API、MCP のファイル更新系ツールなどで、リモートブランチ上のファイルを直接作成・更新・削除しない。
- 変更は必ずローカル作業ツリーで編集し、`git add`、`git commit`、`git push` の通常フローで反映する。
- `git add`、`git commit`、`git push`、`git checkout`、`git reset` などが失敗した場合は、API 等で迂回せず、原因を切り分けてユーザーに確認する。
- GitHub API は Issue/PR の作成、コメント、メタ情報更新、状態確認など、ファイル内容を直接変更しない操作に限って使用する。

## 設計方針
- 基本的に DDD（ドメイン駆動設計）のエッセンスに沿って設計・実装する。
- `domain/` 配下は基本的に Repository、Service、Value Object の3層で構成する。
- 業務ルールや判断ロジックは、可能な限り `domain/` 配下の Value Object、Service、Repository に集約する。
- Django の `views.py`、`forms.py`、`models.py` はフレームワーク連携や入出力、永続化の責務を中心にし、業務ロジックを過度に持たせない。
- Repository は永続化の詳細を隠蔽し、Service が Django モデルのクエリ操作に直接依存しないようにする。
- UseCase、Factory など追加の DDD 構造は、必要性が明確な場合にだけ作る。
- 基本の3層で十分な場合は追加の層を作らず、過剰品質を避ける。

## ユーザー管理の設計パターンの統一
- すべてのアプリにおいて、認証（ID/Pass）は Django 標準の `auth.User` を使用し、アプリ固有の属性やロール（役割）の管理は、各アプリ内で `User` と 1:1 で紐づく `UserAttribute` モデル（またはそれに相当するプロフィールモデル）を定義して行う。
- 同一の `User` に対し、アプリごとに異なる役割（例：`hospital` では医師/患者、`shopping` ではスタッフ/購入者）を独立して定義できる構成を維持すること。
- これにより、システム全体の認証基盤を共通化しつつ、各ドメインに特化した柔軟なユーザー属性管理を実現する。

