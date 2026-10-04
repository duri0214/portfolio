# Apache アクセス傾向メールの運用

`lib/apache_access/report_service.py` が Apache ログを直近24時間分集計し、IP、URL、クエリ、ログ行を含まない JSON を作ります。Web 側はこの JSON だけを読み、既存の `MailService` で固定の管理者宛先へ送信します。Django モデル、migration、専用 Django アプリは使用しません。

## 事前準備（一度だけ、サーバー管理者が実施）

以下はプロジェクトを `/var/www/html/portfolio` に配置し、集計を `ubuntu`、Web を `www-data` で実行する場合の手順です。

### 1. Apache のログ形式と出力先を確認する

```bash:console
$ sudo apache2ctl -S
$ sudo grep -R "^[[:space:]]*\(LogFormat\|CustomLog\)" /etc/apache2
```

対象が `/var/log/apache2/access.log` とローテート済みの `access.log.*` であり、`LogFormat` が combined 相当であることを確認します。形式や対象ファイルが不明な場合は cron を登録しません。

### 2. 匿名化済み JSON の保存場所を用意する

生ログは `ubuntu` だけが読みます。匿名化済み JSON と送信間隔の状態ファイルは、`ubuntu` と `www-data` の両方が読み書きできる専用ディレクトリへ置きます。

```bash:console
$ sudo install -d -o ubuntu -g www-data -m 2770 /var/lib/portfolio
$ sudo setfacl -m u:ubuntu:rwx,u:www-data:rwx /var/lib/portfolio
$ sudo setfacl -d -m u:ubuntu:rwx,u:www-data:rwx /var/lib/portfolio
$ sudo -u ubuntu test -w /var/lib/portfolio && echo OK_batch_write || echo NG_batch_write
$ sudo -u www-data test -w /var/lib/portfolio && echo OK_web_write || echo NG_web_write
```

### 3. `.env` を設定する

`/var/www/html/portfolio/.env` に次を設定します。実在するメールアドレスと SMTP 認証情報は Git、Issue、PR、ログへ書きません。

```dotenv:/var/www/html/portfolio/.env
APACHE_ACCESS_LOG_GLOBS=/var/log/apache2/access.log*
APACHE_ACCESS_REPORT_PATH=/var/lib/portfolio/apache_access_report.json
APACHE_REPORT_RECIPIENT=管理者の固定メールアドレス
MAIL_SMTP_HOST=smtp.example.com
MAIL_SMTP_PORT=587
MAIL_SMTP_USER=送信用アカウント
MAIL_SMTP_PASSWORD=送信用パスワードまたはアプリパスワード
MAIL_USE_TLS=True
```

```bash:console
$ sudo chown ubuntu:ubuntu /var/www/html/portfolio/.env
$ sudo chmod 600 /var/www/html/portfolio/.env
```

### 4. Apache ログの読み取り権限を確認する

```bash:console
$ sudo namei -l /var/log/apache2/access.log
$ sudo -u ubuntu test -r /var/log/apache2/access.log && echo OK_batch_read || echo NG_batch_read
$ sudo -u www-data test -r /var/log/apache2/access.log && echo NG_web_can_read || echo OK_web_blocked
```

`ubuntu` が対象の `access.log*` だけを読め、`www-data` は読めない状態にします。`ubuntu` を全 Apache ログが読める広いグループへ安易に追加せず、専用グループまたは ACL を使い、ローテーション後も同じ権限が付くようにします。

### 5. Web 側の変更を反映する

この機能に migration はありません。

```bash:console
$ sudo apache2ctl configtest
# 期待値: Syntax OK
$ sudo systemctl restart apache2
```

## 集計処理の確認と cron 登録

cron はメール送信には使いません。生ログを読める `ubuntu` が匿名化済み JSON を更新し、生ログを読めない `www-data` がブラウザ操作時にその JSON をメール送信するために使います。サーバーへログインして送信前に毎回手動集計する運用なら cron は省略できますが、「サーバーへログインせずに送信する」という Issue #954 の要件では定期更新が必要です。

最初に `ubuntu` で1回だけ手動実行します。

```bash:console
$ sudo -u ubuntu -H bash -lc 'cd /var/www/html/portfolio && .venv/bin/python -m lib.apache_access.report_service'
# 期待値: Apache アクセス集計を保存しました。
$ sudo -u www-data test -r /var/lib/portfolio/apache_access_report.json && echo OK_web_read || echo NG_web_read
```

成功したら cron のログを用意し、`ubuntu` の crontab に1時間ごとの処理を1行だけ登録します。

```bash:console
$ sudo install -d -o ubuntu -g ubuntu -m 750 /var/log/portfolio
$ sudo touch /var/log/portfolio/apache-access-report.log
$ sudo chown ubuntu:ubuntu /var/log/portfolio/apache-access-report.log
$ sudo chmod 640 /var/log/portfolio/apache-access-report.log
$ sudo -u ubuntu crontab -e
```

```vim:crontab
0 * * * * cd /var/www/html/portfolio && /var/www/html/portfolio/.venv/bin/python -m lib.apache_access.report_service >> /var/log/portfolio/apache-access-report.log 2>&1
```

```bash:console
$ sudo -u ubuntu crontab -l | grep lib.apache_access.report_service
```

## メール送信操作

1. cron または手動集計が成功していることを確認する。
2. portfolio にスーパーユーザーでログインする。
3. 共通ナビバーの「アクセス集計をメール送信」を1回押す。
4. 専用画面へ移動せず元のページに「集計メールを送信しました。」と通知され、固定宛先へ対象期間・生成時刻・件数を含む HTML/プレーンテキストメールが届くことを確認する。

同じ操作を15分以内に繰り返すと再送を拒否します。未ログイン・一般ユーザー・スタッフユーザーも送信できません。

## 失敗時の確認順

1. 「宛先が設定されていません」: `APACHE_REPORT_RECIPIENT` を確認する。
2. 「集計結果がありません」「集計結果が古い」: cron ログと `/var/lib/portfolio/apache_access_report.json` の更新時刻を確認する。
3. 集計コマンドが失敗: `APACHE_ACCESS_LOG_GLOBS`、combined 形式、`ubuntu` のログ読み取り権限を確認する。
4. メール送信が失敗: `MAIL_SMTP_*`、TLS、宛先、Apache のエラーログを確認する。SMTP パスワードや生ログは Issue・PRへ貼らない。
5. 修正後は、手動集計を実行してからブラウザの送信操作を再実行する。
