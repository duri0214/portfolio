# create-branch-from-issue

GitHub Issueの内容を確認し、特定の命名規則に従って master ブランチから新しい作業ブランチを作成します。

## 実行ステップ (日本語で対話してください)

1. **GitHub Issueの特定と確認**
    - **まず最初に**、ユーザーからGitHub Issue番号またはURLを日本語で聞き出します（`ask_user` ツールを使用）。
    - URL形式: `https://github.com/{owner}/{repo}/issues/{number}`
    - `gh issue view <issue-no> --json number,title,body,labels` を実行して、Issueの詳細（タイトル、内容、ラベル）を確認します。
    - 必要に応じて、自分をアサインし、プロジェクト `yoshi` を設定します：
        - `gh issue edit <issue-no> --add-assignee "@me" --add-project "yoshi"`

2. **ブランチタイプの決定**
    - Issueの内容やラベル、ユーザーへのヒアリングに基づき、ブランチタイプを選択します：
        - `feature`: 新機能、機能追加
        - `hotfix`: 緊急のバグ修正
        - `bugfix`: 通常のバグ修正
        - `chore`: 雑務、構成変更
        - `docs`: ドキュメント作成・更新
    - UIの選択肢からブランチタイプを選択、またはユーザーに確認を求めます。

3. **ブランチ名の生成**
    - 命名規則: `<issue-no>-<branch-type>-<description>`
    - `<description>` はIssue의タイトルを以下のルールでサニタイズして作成します：
        - 小文字に変換
        - スペースをハイフンに置換
        - 特殊文字を削除
        - 最大50文字程度に制限
    - ブランチタイプと内容が重複しないように注意してください（例：`bugfix-fix-` ではなく `bugfix-` から始める）。
    - 例: `545-bugfix-login-error`, `551-feature-user-profile`

4. **ブランチの作成とチェックアウト**
    - `master` ブランチに切り替え、最新の状態にします。
        ```powershell
        git checkout master
        git pull origin master
        ```
    - 新しいブランチを作成してチェックアウトします。
        ```powershell
        git checkout -b <branch-name>
        ```

5. **作業着手の確認とプロジェクトステータスの更新**
    - ブランチ作成が完了したら、実装作業（修正）に着手するかを日本語でUIのボタンや選択肢（はい/いいえ）で確認します。
    - ユーザーから承諾が得られた場合：
        - GitHub Projects の Status を `In progress` に更新します。
        - 実際のコード修正ステップ（または該当する別のスキル）へ進みます。
    - 拒否された場合は、そこで処理を中断または終了します。

6. **完了報告**
    - 作成したブランチ名と、対象となったIssueの情報を報告します。

## 注意事項
- `gh` コマンド（GitHub CLI）がインストールされ、ログインしている必要があります。
- 作業は必ず `master` ブランチ（またはプロジェクトのメインブランチ）から分岐させてください。
- Issue本文に「担当：TBD」などの不要な項目が含まれている場合は、編集して削除することを推奨します。
