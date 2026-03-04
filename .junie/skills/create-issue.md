# Create Issue Skill

## 概要
課題や新機能、バグ修正などのタスクを管理するために、GitHub Issueを新規作成します。
標準的なテンプレートに基づき、背景、目的、受け入れ条件などを整理して登録します。

## 実行ステップ

1. **Issue情報の整理**
    - ユーザーからIssueの内容（タイトル、背景、目的、受け入れ条件など）を聞き出します。
    - 不足している情報があればヒアリングして補完します。

2. **本文テンプレートの適用**
    - 以下の構造でMarkdown形式の本文を作成します（見出しには `##` を使用）。
    - 担当者（Assignee）は自分（@me）とするため、本文に「担当：TBD」などは含めません。

    ```markdown
    ## 背景
    (なぜこの課題が必要か、現状の課題など)

    ## 目的
    (このIssueで何を達成するか)

    ## 受け入れ条件
    - [ ] (具体的な完了条件1)
    - [ ] (具体的な完了条件2)

    ## 備考
    (参考URLや補足事項など)
    ```

3. **Issueの作成**
    - `gh issue create` コマンドを使用してIssueを作成します。
    - 必要に応じてラベル（`bug`, `feature`, `hotfix`, `chore`, `docs` など）を付与します。
    - **特定の性質を持つラベルの付与**:
        - 10分〜30分程度で簡単に終わりそうだと判断できたら、`good first issue` ラベルを付与します。
        - 調査が必要な内容であれば、`調査` ラベルを付与します。
    - **優先度の確認**：ユーザーに確認し、以下のラベルを付与します。
        - `優先度: 低`
        - `優先度: 中`
        - `優先度: 高`
    - 自分をアサインします（`--assignee @me`）。
    - プロジェクトには `yoshi` を指定します（`--project yoshi`）。
    - **親子関係（Relationships）の設定**:
        - 親チケットや関連するチケットがある場合は、`gh issue edit <issue-no> --add-parent <parent-issue-no>` などを使用して関係を設定します（または本文の「備考」欄にリンクを記載します）。

    ```powershell
    # コマンド例（本文をファイルに保存して作成する場合）
    # $body | Out-File -FilePath issue_body.txt -Encoding utf8
    gh issue create --title "タイトル" --body-file issue_body.txt --label "feature","good first issue","優先度: 中" --assignee @me --project yoshi
    ```

4. **完了報告**
    - 作成されたIssueの番号とURLを報告します。ユーザーが内容を直接確認したり、追加の編集を行えるようにURLを提示してください。

## 注意事項
- `gh` コマンド（GitHub CLI）がインストールされ、ログインしている必要があります。
- **日本語の文字化け対策**: 
    - 本文ファイルを一時的に作成する場合は、必ず **UTF-8（BOMなし）** エンコーディングで保存してください。
    - PowerShell の場合、`Out-File -Encoding utf8` や `Set-Content -Encoding utf8` を使用して保存し、`gh issue create --body-file` で読み込ませてください。
- 既存のIssueと重複していないか事前に確認してください。
