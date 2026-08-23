# MailService

`MailService` は、SMTPへ接続してメールを送信するための共通ライブラリです。
DjangoのUser、View、URL、セッションには依存しないため、Djangoアプリ以外からも単独で利用できます。

## 責務

### `lib/mail`

- SMTP接続、TLS開始、認証、メール送信
- プレーンテキスト・HTMLメールの作成
- SMTP設定の読み込みと設定不足・送信失敗の通知

以下の処理は担当しません。

- ユーザー作成やパスワード管理
- 仮登録状態や本登録状態の管理
- 認証トークンの発行・検証
- 認証URLの生成
- 送信するかどうかというアプリケーション上の判断

### `accounts`

`accounts` は会員登録とメール認証の業務フローを担当します。

1. メールアドレスとパスワードでDjango標準Userを仮登録する
2. 本登録用の期限付き認証URLを生成する
3. `ACCOUNT_EMAIL_SEND_ENABLED` が有効な場合だけ `MailService` に送信を依頼する
4. 認証URLの検証後にUserを有効化する

つまり、`accounts` が「何を、いつ送るか」を決め、`MailService` が「SMTPで送る」部分だけを担当します。

## 設定

### 単独利用

このディレクトリの `.env.example` を `.env` としてコピーし、SMTP設定を入力します。

```text
MAIL_SMTP_HOST=smtp.example.com
MAIL_SMTP_PORT=587
MAIL_SMTP_USER=sender@example.com
MAIL_SMTP_PASSWORD=********
MAIL_USE_TLS=True
```

### Djangoから利用

プロジェクトルートの `.env` に同じ `MAIL_SMTP_*` 設定を記述できます。
`config/settings.py` がルートの `.env` を先に読み込むため、Django実行時はその設定が利用されます。

`MailService` は、すでに設定されている環境変数を上書きしません。単独実行時は
`lib/mail/.env` を先に読み込み、プロジェクトルートの `.env` で不足分を補います。

`ACCOUNT_EMAIL_SEND_ENABLED` は `MailService` の設定ではありません。これは `accounts` が実送信を許可するか判断するためのDjango設定で、初期値は `False` です。
`False` の場合、`accounts` は `MailService` を呼び出さず、SMTPにも接続しません。
この場合は仮登録ユーザーを `is_active=False` で保持し、画面にも本登録URLを表示しないため、本登録前のログインはできません。

## 単独利用の例

```python
from lib.mail.mail_service import MailService

service = MailService()
service.send_mail(
    to="user@example.com",
    subject="テストメール",
    body="本文です。",
)
```

HTML本文を追加する場合は `html_body` を指定します。

```python
service.send_mail(
    to="user@example.com",
    subject="HTMLメール",
    body="HTMLを表示できない環境向けの本文です。",
    html_body="<p>HTML本文です。</p>",
)
```

設定不足の場合は `ValueError`、SMTP接続や送信に失敗した場合は `MailSendError` が発生します。
実際のSMTPへ送信する前に、テストでは `smtplib.SMTP` をモックしてください。

```powershell
python -m unittest lib.mail.test_mail_service -v
```

SMTP認証情報は `.env` に記述し、Gitへコミットしないでください。
