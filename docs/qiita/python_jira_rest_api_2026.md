# PythonでシンプルにJiraからチケット情報を取得・CRUDする2026

## はじめに

現場でJiraを使う機会が増えたので、[Jira Cloud REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/) を Python から素朴に呼び出す形で整理します。

2025版では「プロジェクト一覧を取る」「チケット一覧を取る」ところまででしたが、今回は [Issue #236](https://github.com/duri0214/portfolio/issues/236) の内容に沿って、Pythonからチケットの作成・取得・編集・削除まで扱えるようにしました。

この記事は2段構成です。

1. Python + `requests` で Jira REST API のCRUDを理解する
2. AI時代の運用として、JiraコネクタやCodexスキルから同じ操作を扱う

## 参考

- [Jira Cloud platform REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
- [Manage API tokens for your Atlassian account](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)
- [Basic auth for REST APIs](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/)
- [Issue #236: lib: jiraライブラリにCRUDをつける](https://github.com/duri0214/portfolio/issues/236)
- [実際に確認したPR #789](https://github.com/duri0214/portfolio/pull/789)

## Jira側でAPIトークンを生成する

Jira Cloud の REST API は、Atlassianアカウントのログインパスワードではなく、APIトークンを使って認証します。

PythonからAPIを呼び出すときは、次の3つを用意します。

- Jiraサイトのドメイン: `https://<your-domain>.atlassian.net` の `<your-domain>` 部分
- Atlassianアカウントのメールアドレス
- Atlassianアカウントで発行したAPIトークン

これらはローカルの `.env` に保存します。APIトークンやメールアドレスを記事やコードに直書きしないようにします。

公式ドキュメントによると、2024年12月15日以降に作成したAPIトークンはデフォルトで1年の有効期限が設定されます。古いトークンも期限切れになる場合があるため、`401 Client must be authenticated` が返る場合は、まずトークンが失効していないか確認します。

APIトークンの発行手順は以下です。

1. https://id.atlassian.com/manage-profile/security/api-tokens にログインする。
2. `Create API token` を選択する。
3. APIトークンの用途が分かる名前を付ける。
4. 有効期限を選択する。
5. `Create` を選択する。
6. 表示されたトークンをコピーして、安全な場所に保存する。

トークンは作成直後にしか表示されません。コピーし忘れた場合やリセットした場合は、古いトークンを使い回さず、新しいトークンを作り直します。

PythonからJira REST APIを呼ぶときは、AtlassianアカウントのメールアドレスとAPIトークンをBasic認証に使います。パスワードではなくAPIトークンを渡すのがポイントです。

```dotenv:lib/jira/.env.example
JIRA_YOUR_DOMAIN=
JIRA_USER_EMAIL=
JIRA_API_KEY=
```

`.env` には以下のように対応させます。

- `JIRA_YOUR_DOMAIN`: `https://<your-domain>.atlassian.net` の `<your-domain>` 部分
- `JIRA_USER_EMAIL`: Atlassianアカウントのメールアドレス
- `JIRA_API_KEY`: 発行したAPIトークン

## 実装方針

https://github.com/duri0214/portfolio/tree/master/lib/jira

`lib/jira/` に置いている `jira_service.py` の `JiraService` は、Jira REST API v3 の薄いラッパーです。

- `fetch_projects`: プロジェクト一覧を取得
- `fetch_issues`: プロジェクト配下のTask一覧を取得
- `fetch_issue`: チケット1件を取得
- `create_issue`: チケットを作成
- `update_issue`: チケットを編集
- `delete_issue`: チケットを削除

Jira Cloud のチケット本文 `description` は単純な文字列ではなく、Jira Document Format のJSONとして送ります。今回の実装では、最小限の paragraph/text 形式に変換しています。

## CRUDで使うエンドポイント

```text
GET    /rest/api/3/project/search
GET    /rest/api/3/search
GET    /rest/api/3/issue/{issueIdOrKey}
POST   /rest/api/3/issue
PUT    /rest/api/3/issue/{issueIdOrKey}
DELETE /rest/api/3/issue/{issueIdOrKey}
```

DELETE は破壊的な操作なので、必ず検証用プロジェクトや検証用チケットで試します。サブタスクも削除したい場合は `deleteSubtasks=true` を付けます。

## 作成ペイロード

```python:lib/jira/valueobject/ticket.py
payload = CreateIssuePayload(
    summary="Main order flow broken",
    project_key="HEN",
    issue_type_id="10000",
    description_text="Order entry fails when selecting supplier.",
    labels=["bugfix"],
)
```

`CreateIssuePayload.to_dict()` で Jira API が期待する `fields` 形式へ変換します。任意項目は指定されたときだけ送るため、最小構成では `summary`, `project`, `issuetype` だけになります。

## チケットを作成する

```python:lib/jira/jira_service.py
def create_issue(self, payload: CreateIssuePayload) -> dict:
    url = f"{self.base_url}/rest/api/3/issue"
    response = requests.post(
        url,
        headers=self.headers,
        auth=self.auth,
        json=payload.to_dict(),
    )
    response.raise_for_status()
    return response.json()
```

作成に成功すると、Jiraから `id`, `key`, `self` が返ります。

## チケットを取得する

一覧は `fetch_issues(project_key)`、1件だけ見る場合は `fetch_issue(issue_key)` を使います。

```python:lib/jira/jira_service.py
issue = jira_service.fetch_issue("HEN-1")
```

一覧取得では、既存実装と同じく Jira のレスポンスから `IssueVO` に詰め替えています。1件取得は後続の履歴保存やLLM分析で情報を落とさないよう、生のJSONを返す形にしています。

## チケットを編集する

```python:lib/jira/valueobject/ticket.py
payload = UpdateIssuePayload(
    summary="Main order flow fixed",
    labels=["done"],
)
```

```python:lib/jira/jira_service.py
jira_service.update_issue("HEN-1", payload)
```

Jiraの編集APIは成功時に本文を返さないため、HTTPエラーがなければ `None` のまま終了します。

## チケットを削除する

```python:lib/jira/jira_service.py
jira_service.delete_issue("HEN-1", delete_subtasks=True)
```

削除は取り消しが難しいため、検証用チケットで動作確認してから使います。

## テスト

外部APIを直接叩かないように、`requests.get/post/put/delete` をモックして確認しています。

```bash:console
$ python -m unittest lib.jira.test_jira_service
```

確認していることは以下です。

- チケット一覧・単一チケットを取得できる
- チケット作成APIへ期待したJSONをPOSTする
- チケット編集APIへ期待したJSONをPUTする
- チケット削除APIへ `deleteSubtasks` を渡してDELETEする
- 作成/更新ペイロードがJira Document Formatへ変換される

## AI時代の補足: Jiraコネクタやスキルから扱う

ここまでの実装は「Jira REST APIを理解して、自分のアプリから扱う」ためのものです。一方で、AIエージェントと一緒に作業するなら、JiraコネクタやCodexスキル経由で同じような操作を扱う選択肢もあります。

たとえば、運用としては次の2層に分けると扱いやすいです。

1. アプリ側の責務: `lib/jira/` でCRUD、履歴スナップショット保存、JSON化を行う
2. AI側の責務: Jiraコネクタ/スキルでチケットを読み、要約、分類、実装ブランチ作成、PR作成までつなぐ

アプリ側にCRUDを持っておくと、ログ保存や分析の再現性を確保できます。AI側にコネクタを持たせると、チケットの文脈を読みながら作業手順へ落とし込めます。

この記事では、PythonからJira REST API v3を呼び出し、チケットの作成・取得・編集・削除まで確認しました。まずはこのCRUDが動けば、Jira上のチケットをPythonから扱う土台としては十分です。
