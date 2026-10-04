# ApacheAccessReportService

`lib/apache_access` は、Apache のアクセスログを匿名化した件数へ集計し、既存の `MailService` で管理者へ送信する共通ライブラリです。Djangoアプリ、Djangoモデル、migration、専用画面は追加しません。

## ファイルと責務

- `report_service.py`: cron から呼ぶ集計 CLI の入口
- `domain/valueobject/report.py`: 匿名化された集計値とドメイン例外
- `domain/service/access_log_aggregator.py`: Apache combined ログの解析・集計
- `domain/service/report_service.py`: JSON 保存、鮮度・再送制限、`MailService` 呼び出し
- `domain/service/report_mail.py`: プレーンテキスト・HTML本文の生成
- `report_receiver.py`: 共通ナビバーからのPOSTを受け、CSRF・スーパーユーザーを確認し、送信結果を操作元へ返す Django アダプター
- `test_report_service.py`: 集計、保存、送信、権限、Web 操作のテスト

`config/urls.py` は送信URLと `report_receiver.py` を接続するだけです。共通ナビバーのボタンがこの入口をPOSTで呼び出します。`home` はこの処理を担当しません。

## `.env` の場所

このライブラリが読む `.env` は、**リポジトリ直下の `manage.py` と同じディレクトリにある `.env`** です。`lib/apache_access/.env` ではありません。

- 本番配置が `/var/www/html/portfolio` の場合: `/var/www/html/portfolio/.env`
- ローカル環境の場合: チェックアウトした `portfolio` ディレクトリ直下の `.env`

`domain/service/report_service.py` は自身の場所からリポジトリルートを求め、このファイルを明示的に読み込みます。

`APACHE_REPORT_RECIPIENT` はブラウザ操作で送る固定の受信先なので必須です。管理者や運用担当が受信するメールアドレス（例: `ops@example.com`）を設定し、SMTPの送信元アカウントとは分けて考えます。

`APACHE_ACCESS_LOG_GLOBS` は任意です。未設定なら `/var/log/apache2/access.log*` を使います。`*` は現在の `access.log` と `access.log.1` などのローテーション済みファイル、`access.log.2.gz` などのgzipファイルを含みます。複数の場所を読む場合はカンマ区切りで指定します。

`APACHE_ACCESS_REPORT_PATH` も任意ですが、本番では `ubuntu`（集計）と `www-data`（ブラウザ送信）が共有できる `/var/lib/portfolio/apache_access_report.json` を明示してください。未設定時はローカル開発用のリポジトリ直下 `.private/apache_access_report.json` に保存します。

`MAIL_SMTP_*` と `MAIL_USE_TLS` は既存の `MailService` の設定を使います。`lib/mail/.env` が存在する環境ではそちらが先に読み込まれるため、SMTP設定を重複させず、既存の設定場所を使用してください。

## 事前準備（一度だけ、サーバー管理者が実施）

以下は、リポジトリを `/var/www/html/portfolio` に配置し、集計を `ubuntu`、Web を `www-data` で実行する場合の手順です。

### 1. Apache のログ形式と出力先を確認する

```bash
sudo apache2ctl -S
sudo grep -R "^[[:space:]]*\(LogFormat\|CustomLog\)" /etc/apache2
```

対象が `/var/log/apache2/access.log` とローテート済みの `access.log.*` であり、`LogFormat` が combined 相当であることを確認します。

### 2. 匿名化済み JSON の保存場所を用意する

生ログは `ubuntu` だけが読みます。匿名化済み JSON と送信間隔の状態ファイルは、`ubuntu` と `www-data` の両方が読み書きできる専用ディレクトリへ置きます。

```bash
sudo apt install acl -y
sudo install -d -o ubuntu -g www-data -m 2770 /var/lib/portfolio
sudo setfacl -m u:ubuntu:rwx,u:www-data:rwx /var/lib/portfolio
sudo setfacl -d -m u:ubuntu:rwx,u:www-data:rwx /var/lib/portfolio
sudo -u ubuntu test -w /var/lib/portfolio && echo OK_batch_write || echo NG_batch_write
sudo -u www-data test -w /var/lib/portfolio && echo OK_web_write || echo NG_web_write
```

### 3. `/var/www/html/portfolio/.env` を設定する

```dotenv
APACHE_ACCESS_LOG_GLOBS=/var/log/apache2/access.log*
APACHE_ACCESS_REPORT_PATH=/var/lib/portfolio/apache_access_report.json
APACHE_REPORT_RECIPIENT=ops@example.com
MAIL_SMTP_HOST=smtp.example.com
MAIL_SMTP_PORT=587
MAIL_SMTP_USER=送信用アカウント
MAIL_SMTP_PASSWORD=送信用パスワードまたはアプリパスワード
MAIL_USE_TLS=True
```

実在するメールアドレスと SMTP 認証情報は Git、Issue、PR、ログへ書きません。

```bash
sudo chown ubuntu:www-data /var/www/html/portfolio/.env
sudo chmod 640 /var/www/html/portfolio/.env
sudo -u ubuntu test -r /var/www/html/portfolio/.env && echo OK_batch_env || echo NG_batch_env
sudo -u www-data test -r /var/www/html/portfolio/.env && echo OK_web_env || echo NG_web_env
```

### 4. Apache ログの読み取り権限を確認する

```bash
sudo namei -l /var/log/apache2/access.log
sudo -u ubuntu test -r /var/log/apache2/access.log && echo OK_batch_read || echo NG_batch_read
sudo -u www-data test -r /var/log/apache2/access.log && echo NG_web_can_read || echo OK_web_blocked
```

`ubuntu` が対象の `access.log*` だけを読め、`www-data` は読めない状態にします。ローテーション後も同じ権限が付くように、専用グループまたは ACL を設定します。

### 5. Web 側へ変更を反映する

この機能に migration はありません。

```bash
sudo apache2ctl configtest
sudo systemctl restart apache2
```

`apache2ctl configtest` の期待値は `Syntax OK` です。

## 集計処理を手動確認する

```bash
sudo -u ubuntu -H bash -lc 'cd /var/www/html/portfolio && .venv/bin/python -m lib.apache_access.report_service'
sudo -u www-data test -r /var/lib/portfolio/apache_access_report.json && echo OK_web_read || echo NG_web_read
```

集計コマンドの成功時は `Apache アクセス集計を保存しました。` と出力して終了コード0、失敗時は原因を出力して終了コード1を返します。JSON には日時と件数だけを保存し、IP、URL、クエリ、ログ行は保存しません。

## 定期集計を登録する

cron はメール送信には使いません。生ログを読める `ubuntu` が匿名化済み JSON を更新し、生ログを読めない `www-data` がブラウザ操作時にその JSON をメール送信するために使います。

送信前にサーバーへログインして毎回手動集計する運用なら cron は省略できます。「サーバーへログインせずブラウザから送信する」運用では、cron などによる定期更新が必要です。

```bash
sudo install -d -o ubuntu -g ubuntu -m 750 /var/log/portfolio
sudo touch /var/log/portfolio/apache-access-report.log
sudo chown ubuntu:ubuntu /var/log/portfolio/apache-access-report.log
sudo chmod 640 /var/log/portfolio/apache-access-report.log
sudo -u ubuntu crontab -e
```

`ubuntu` の crontab に次の1行を登録します。

```cron
0 * * * * cd /var/www/html/portfolio && /var/www/html/portfolio/.venv/bin/python -m lib.apache_access.report_service >> /var/log/portfolio/apache-access-report.log 2>&1
```

```bash
sudo -u ubuntu crontab -l | grep lib.apache_access.report_service
```

## メールを送信する

1. 手動集計または cron が成功していることを確認する。
2. portfolio にスーパーユーザーでログインする。
3. 共通ナビバーの「アクセス集計をメール送信」を1回押す。
4. 元のページに「集計メールを送信しました。」と通知されることを確認する。
5. 固定宛先へ、対象期間、生成時刻、件数を含む HTML・プレーンテキストメールが届くことを確認する。

同じ操作を15分以内に繰り返すと再送を拒否します。未ログイン、一般ユーザー、スタッフユーザーは送信できません。

## 失敗時の確認順

1. 「宛先が設定されていません」: `/var/www/html/portfolio/.env` の `APACHE_REPORT_RECIPIENT` を確認する。
2. 「集計結果がありません」「集計結果が古い」: `/var/log/portfolio/apache-access-report.log` と `/var/lib/portfolio/apache_access_report.json` の更新時刻を確認する。
3. 集計コマンドが失敗: `APACHE_ACCESS_LOG_GLOBS`、combined 形式、`ubuntu` のログ読み取り権限を確認する。
4. メール送信が失敗: `MAIL_SMTP_*`、TLS、宛先、Apache のエラーログを確認する。
5. 修正後、手動集計を実行してからブラウザの送信操作を再実行する。

SMTP パスワード、生ログ、実在する宛先は Issue や PR へ貼りません。
