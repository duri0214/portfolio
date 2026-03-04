# Commit and PR Creation Skill

## 概要
修正ごとにコミットを行い、リモートブランチへプッシュし、プルリクエスト（PR）を作成する一連のワークフローを定義します。

## 実行ステップ

1. **コミットの実行**
    - 修正内容ごとにコミットを行います（大きな変更を一度にコミットせず、論理的な単位で分割します）。
    - `git commit --amend` は使用せず、新しいコミットを追加していきます。
    - コミットメッセージの形式：
        - `feat: <description>` (新機能)
        - `fix: <description>` (バグ修正)
        - `docs: <description>` (ドキュメント)
        - `chore: <description>` (雑務)
        - `refactor: <description>` (リファクタリング)
    - 必要に応じて Issue 番号を含めます（例: `fix: ログインエラーの修正 (#545)`）。

2. **プッシュの実行**
    - `git push origin <branch-name>` を実行してリモートブランチを更新します。

3. **プルリクエスト（PR）の作成**
    - `gh pr create` コマンドを使用してPRを作成します。
    - 担当者（Assignee）は自分 (`--assignee @me`) に設定します。
    - ラベル（Labels）とプロジェクト（Projects）は、元となる Issue に設定されているものを指定します。
    - タイトル：`[<branch-type>] <issue-title> (#<issue-no>)`
    - 本文：
        ```markdown
        ## 概要
        (今回の変更内容を簡潔に記述)

        ## 変更内容
        - (具体的な変更点1)
        - (具体的な変更点2)

        ## 関連Issue
        - Closes #<issue-no>
        ```
    - ベースブランチは `master` とします（`--base master`）。

    ```powershell
    # コマンド例
    gh pr create --title "[feature] junie用のskill作成 (#556)" --body-file pr_body.txt --base master --assignee @me --label "hotfix" --project "yoshi"
    ```

4. **完了報告**
    - 作成されたPRのURLを報告します。ユーザーがクリックして直接確認・レビュー・マージなどの操作を行えるように、URLを明確に提示してください。

## 注意事項
- 修正ごとにこまめにコミットしてください。
- `gh` コマンドがインストールされ、ログインしている必要があります。
- **日本語の文字化け対策**: 
    - PRのタイトルや本文に文字化けが発生しないよう注意してください。
    - 本文ファイルを一時的に作成する場合は、必ず **UTF-8（BOMなし）** エンコーディングで保存してください。
    - PowerShell の `Out-File -Encoding utf8` は **BOMあり** になるため使用せず、Python スクリプトで `encoding='utf-8'` を指定して書き出すか、環境に応じて BOM なしを保証する手段を講じてください。
    - `gh pr create --body-file` で読み込ませる際、BOM があると GitHub 上で正しく表示されない場合があります。
- **PRのマージ禁止**: JunieはPRの作成までを担当し、**勝手にマージを行ってはいけません**。ユーザーによるレビューとマージを待つか、明示的な指示がある場合のみマージを検討してください。
