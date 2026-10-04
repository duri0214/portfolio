# ApacheAccessReportService

`lib/apache_access` は、Apache のアクセスログを匿名化した件数へ集計し、既存の `MailService` で管理者へ送信する共通ライブラリです。Djangoアプリ、Djangoモデル、migration、専用画面は追加しません。

## `.env` の場所

Apache固有の設定は、リポジトリ直下の `.env` に設定します。たとえば本番配置が `/var/www/html/portfolio` の場合は `/var/www/html/portfolio/.env`、ローカル環境ではチェックアウトした `portfolio` ディレクトリ直下の `.env` を使用します。

メールの送信先は追加の環境変数を使わず、既存の `lib/mail/.env` にある `MAIL_SMTP_USER` を使います。`lib/mail/.env.example` を `lib/mail/.env` にコピーし、`MAIL_SMTP_USER` にレポートを受信する管理者・運用担当のメールボックス（例: `ops@example.com`）を設定してください。SMTPの送信元と同じメールボックスへ送る前提です。

`APACHE_ACCESS_LOG_GLOBS` は任意です。未設定なら `/var/log/apache2/access.log*` を使います。`*` は現在の `access.log` と `access.log.1` などのローテーション済みファイル、`access.log.2.gz` などのgzipファイルを含みます。複数の場所を読む場合はカンマ区切りで指定します。

`MAIL_SMTP_*` と `MAIL_USE_TLS` は既存の `MailService` の設定を使います。`lib/mail/.env` が存在する環境ではそちらが先に読み込まれるため、SMTP設定を重複させず、既存の設定場所を使用してください。

## 事前準備（一度だけ、サーバー管理者が実施）

以下は、リポジトリを `/var/www/html/portfolio` に配置し、Web を `www-data` で実行する場合の手順です。

### 1. Apache のログ形式と出力先を確認する

```bash
sudo apache2ctl -S
sudo grep -R "^[[:space:]]*\(LogFormat\|CustomLog\)" /etc/apache2
```

対象が `/var/log/apache2/access.log` とローテート済みの `access.log.*` であり、`LogFormat` が combined 相当であることを確認します。

### 2. Apacheログを読み取り専用で確認する

ブラウザ送信時のWebプロセスは、Apacheログを読み取って集計し、結果をメモリ上でメール送信します。ログや集計結果の保存先は用意しません。`www-data` には対象ログへの読み取り権限だけを付与します。

```bash
sudo setfacl -m u:www-data:rx /var/log/apache2
sudo setfacl -m u:www-data:r /var/log/apache2/access.log*
sudo -u www-data test -r /var/log/apache2/access.log && echo OK_web_read || echo NG_web_read
```

### 3. `/var/www/html/portfolio/.env` を設定する

```dotenv
APACHE_ACCESS_LOG_GLOBS=/var/log/apache2/access.log*
```
メール設定は既存の `lib/mail/.env.example` を `lib/mail/.env` にコピーして設定します。`MAIL_SMTP_USER` がSMTP送信元と固定宛先を兼ねます。

```dotenv
MAIL_SMTP_HOST=smtp.example.com
MAIL_SMTP_PORT=587
MAIL_SMTP_USER=ops@example.com
MAIL_SMTP_PASSWORD=app-password
MAIL_USE_TLS=True
```

```bash
sudo chown ubuntu:www-data /var/www/html/portfolio/.env
sudo chmod 640 /var/www/html/portfolio/.env
sudo -u www-data test -r /var/www/html/portfolio/.env && echo OK_web_env || echo NG_web_env
sudo chown ubuntu:www-data /var/www/html/portfolio/lib/mail/.env
sudo chmod 640 /var/www/html/portfolio/lib/mail/.env
sudo -u www-data test -r /var/www/html/portfolio/lib/mail/.env && echo OK_web_mail_env || echo NG_web_mail_env
```

### 4. Apache ログの読み取り権限を確認する

```bash
sudo namei -l /var/log/apache2/access.log
sudo -u www-data test -r /var/log/apache2/access.log && echo OK_web_read || echo NG_web_read
```

`www-data` が対象の `access.log*` を読み取れる状態にします。書き込み権限は付与しません。ローテーション後も読み取りACLが付くように、logrotateの設定を確認します。

### 5. Web 側へ変更を反映する

この機能に migration はありません。

```bash
sudo apache2ctl configtest
sudo systemctl restart apache2
```

`apache2ctl configtest` の期待値は `Syntax OK` です。

## 集計・送信を手動確認する

```bash
sudo -u ubuntu -H bash -lc 'cd /var/www/html/portfolio && .venv/bin/python -m lib.apache_access.report_service'
```

集計コマンドはログを読み取り、匿名化した件数をメモリ上でメール送信します。成功時は `Apache アクセス集計メールを送信しました。` と出力して終了コード0、失敗時は原因を出力して終了コード1を返します。

## メールを送信する

1. portfolio にスーパーユーザーでログインする。
2. 共通ナビバーの「アクセス集計をメール送信」を1回押す。
3. 元のページに「集計メールを送信しました。」と通知されることを確認する。
4. 固定宛先へ、対象期間、生成時刻、件数を含む HTML・プレーンテキストメールが届くことを確認する。

送信操作はその時点のログを読み取って集計します。未ログイン、一般ユーザー、スタッフユーザーは送信できません。

## 失敗時の確認順

1. 「Apacheアクセスログが見つかりません」: `APACHE_ACCESS_LOG_GLOBS` と `www-data` のログ読み取り権限を確認する。
2. 集計コマンドが失敗: combined 形式、ログローテーション後のACL、Apacheのエラーログを確認する。
3. メール送信が失敗: `lib/mail/.env` の `MAIL_SMTP_*`、TLS、`MAIL_SMTP_USER`、Apacheのエラーログを確認する。
4. 修正後、同じ送信操作を再実行する。
