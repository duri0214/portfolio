---
apply: "docs/qiita/python_jira_rest_api_2025.md"
---

# 編集ルール（スタイルガイド） — Python Jira REST API 2025

適用対象: docs/qiita/python_jira_rest_api_2025.md（このファイル専用）

目的:
- Qiita記事「Pythonでシンプルにjiraからチケット情報を取得する2025」の更新時に、REST API v3、ローカル実装、AI時代の代替手段を読みやすく接続する。
- 記事の元の素朴さを保ちながら、CRUD実装とJiraコネクタ活用の2段構成へ拡張する。

適用スコープ:
- Jira Cloud REST API v3 を `requests` で直接呼ぶ説明
- `lib/jira/` の `JiraService` と Value Object の紹介
- AIエージェントやスキルからJiraコネクタを使う補足
- 非対象: Jira管理画面の詳細な権限設計、OAuth 2.0 の本格実装、LLM分析基盤の詳細設計

## ルール

1) 2段構成を保つ
   - 前半は「Python + requests でCRUDを理解する」記事にする。
   - 後半は「AI時代はJiraコネクタ/スキルから同じ操作を扱える」補足にする。
   - コネクタの話はREST API実装を置き換えるものではなく、運用上の選択肢として書く。

2) 認証情報の扱い
   - `.env.example` には `JIRA_YOUR_DOMAIN`, `JIRA_USER_EMAIL`, `JIRA_API_KEY` のみを載せる。
   - 実ドメイン、実メールアドレス、APIトークン、チケット本文に含まれる機微情報は書かない。
   - APIトークンは環境変数から読む前提にし、コードブロックへ直書きしない。

3) コードブロックの表記
   - コンソール操作は `bash:console` を使う。
   - Pythonファイルは `python:lib/jira/jira_service.py` など、コロン右側に対象ファイル名を付ける。
   - envファイルは `dotenv:lib/jira/.env.example` を使う。
   - 公式APIのエンドポイントは `text` または本文の箇条書きで示し、未検証のcurl例を増やさない。

4) CRUDの説明順
   - Read: `fetch_projects`, `fetch_issues`, `fetch_issue`
   - Create: `create_issue`
   - Update: `update_issue`
   - Delete: `delete_issue`
   - JiraのDELETEは破壊的操作なので、本文では必ず「検証用チケットで試す」注意を入れる。

5) Jira Document Format
   - description は単純な文字列ではなく Jira Document Format に変換して送ることを明記する。
   - 本文では最小の paragraph/text 構造だけを扱い、複雑なADF解説へ広げすぎない。

6) 記事更新と実装の同期
   - 記事に載せるメソッド名・環境変数名・ファイルパスは `lib/jira/` の実装と一致させる。
   - 実装にない機能を「できる」と書かない。未実装の分析やスナップショットは今後の拡張として扱う。

## チェックリスト（レビュー用）
- REST API v3 の CRUD エンドポイントが実装と対応しているか。
- `JIRA_USER_EMAIL` と `EMAIL_HOST_USER` の表記揺れが残っていないか。
- description の Jira Document Format 変換が説明されているか。
- DELETE の注意があるか。
- Jiraコネクタ/スキル活用が「2段目」として整理されているか。
- Issue #236 の目的（履歴・分析への入口）に触れつつ、今回の実装範囲を誇張していないか。
