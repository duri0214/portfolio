# Apache アクセス傾向メールの運用

スーパーユーザーは共通ナビバーから、直近24時間のアクセス傾向を固定の管理者宛先へ送れます。メールには件数、対象期間、生成時刻だけを載せます。集計値は調査のきっかけであり、攻撃や情報漏えいの判定ではありません。

## 事前準備（一度だけ、サーバー管理者が実施）

以下は `/var/www/html/portfolio` に配置し、定期処理ユーザーを既存運用どおり `ubuntu` とする場合の手順です。別の配置先・ユーザーを使う場合は、以降のコマンド中の値をすべて同じ値へ置き換えます。

### 1. Apache のログ形式と出力先を確認する

```bash:console
$ sudo apache2ctl -S
$ sudo grep -R "^[[:space:]]*\(LogFormat\|CustomLog\)" /etc/apache2
```

`CustomLog` の実ファイルが `/var/log/apache2/access.log` とローテート済みの `access.log.*` であること、`LogFormat` が combined 相当であることを確認します。リバースプロキシを使っている場合は、ログ先頭の送信元値が信頼できる実クライアント値か確認します。形式が異なる場合は、コマンドを本番で登録せずに停止します。

### 2. 集計対象とメールを `.env` に設定する

サーバー上の `/var/www/html/portfolio/.env` に次を設定します。SMTP の実値は Git、Issue、PR、ログへ書きません。

```dotenv:/var/www/html/portfolio/.env
APACHE_ACCESS_LOG_GLOBS=/var/log/apache2/access.log*
APACHE_REPORT_RECIPIENT=管理者の固定メールアドレス
MAIL_SMTP_HOST=smtp.example.com
MAIL_SMTP_PORT=587
MAIL_SMTP_USER=送信用アカウント
MAIL_SMTP_PASSWORD=送信用パスワードまたはアプリパスワード
MAIL_USE_TLS=True
```

`APACHE_ACCESS_LOG_GLOBS` は現行ファイルと直近24時間に必要なローテート済みファイルを含む絶対パスの glob にします。VirtualHost が別ファイルへ出力する場合はカンマ区切りで追加します。設定後、`.env` の所有者と権限を確認します。

```bash:console
$ sudo chown ubuntu:ubuntu /var/www/html/portfolio/.env
$ sudo chmod 600 /var/www/html/portfolio/.env
```

### 3. マイグレーションと Apache の設定を反映する

```bash:console
$ cd /var/www/html/portfolio
$ sudo -u ubuntu .venv/bin/python manage.py migrate
$ sudo apache2ctl configtest
# 期待値: Syntax OK
$ sudo systemctl restart apache2
```

`migrate` が失敗した場合は cron を登録しません。`configtest` が `Syntax OK` でない場合も Apache を再起動せず原因を修正します。

### 4. 定期処理ユーザーだけにログの読み取り権限を付与する

Web プロセス（通常 `www-data`）には Apache ログの読み取り権限を付けません。ログディレクトリの実際の所有者・グループを確認し、`ubuntu` が対象の現行・ローテート済みファイルだけを読める状態にします。

```bash:console
$ sudo namei -l /var/log/apache2/access.log
$ sudo -u ubuntu test -r /var/log/apache2/access.log && echo OK_current || echo NG_current
$ sudo -u www-data test -r /var/log/apache2/access.log && echo NG_web_can_read || echo OK_web_blocked
```

`NG_current` の場合は、全ログを読める `adm` グループへ安易に追加せず、Apache/logrotate の専用グループまたは ACL で `access.log` と `access.log.*` だけへ読み取り権限を付与します。ローテーション後にも同じ権限が付くことを確認してから次へ進みます。

## 定期実行の登録（サーバー管理者が一度だけ実施）

まず手動で一回実行し、成功することを確認します。

```bash:console
$ sudo -u ubuntu -H bash -lc 'cd /var/www/html/portfolio && .venv/bin/python manage.py aggregate_apache_access'
# 期待値: Apache アクセス集計を保存しました。
```

ログが見つからない、読めない、形式を解析できない場合は終了コードが失敗になり、既存の集計結果は更新されません。成功を確認したら `ubuntu` の crontab に1時間ごとの行を追加します。

```bash:console
$ sudo install -d -o ubuntu -g ubuntu -m 750 /var/log/portfolio
$ sudo touch /var/log/portfolio/apache-access-report.log
$ sudo chown ubuntu:ubuntu /var/log/portfolio/apache-access-report.log
$ sudo chmod 640 /var/log/portfolio/apache-access-report.log
$ sudo -u ubuntu crontab -e
```

```vim:crontab
0 * * * * cd /var/www/html/portfolio && /var/www/html/portfolio/.venv/bin/python manage.py aggregate_apache_access >> /var/log/portfolio/apache-access-report.log 2>&1
```

`/var/log/portfolio` が存在し、`ubuntu` が書き込めることを先に確認します。登録後は次のコマンドで行が残っていることを確認します。

```bash:console
$ sudo -u ubuntu crontab -l | grep aggregate_apache_access
```

cron の実行時刻は、既存のバッチと重ならない時刻へ変更して構いません。変更する場合も、1時間に1回を上限とし、同じコマンドを二重登録しません。

## 毎回のメール送信操作（スーパーユーザーがブラウザで実施）

1. cron または手動実行が成功したことを確認する。
2. portfolio にスーパーユーザーでログインする。
3. 共通ナビバーの「アクセス集計をメール送信」を1回だけ押す。
4. 「集計メールを送信しました。」と表示され、固定宛先へ期間・生成時刻・件数を含む HTML/プレーンテキストメールが届くことを確認する。

同じ操作を15分以内に繰り返すと HTTP 429 相当の再送抑止画面になります。未ログイン・一般ユーザー・スタッフユーザーは送信できません。`APACHE_REPORT_RECIPIENT` が未設定の場合は「宛先が設定されていません。」と表示されます。

## 失敗時の確認順

1. 画面が「集計結果がありません」「集計結果が古い」と表示する場合、cron の実行結果と `home_apacheaccessreport` の生成時刻を確認する。
2. `aggregate_apache_access` が失敗する場合、`APACHE_ACCESS_LOG_GLOBS`、combined 形式、ログファイルの読み取り権限を確認する。
3. SMTP 送信が失敗する場合、`MAIL_SMTP_*`、TLS、送信先アドレス、Apache のエラーログを確認する。SMTP パスワードやログ行を画面・Issue・PRへ貼り付けない。
4. 設定を直した後、手動集計 → スーパーユーザーの送信操作の順に再実行する。

Web 側の送信失敗は HTTP 502、設定不足・集計なし・古い集計は HTTP 503、15分以内の再送は HTTP 429 で表示します。生ログは Web アプリへ渡さず、メールと保存結果にも IP、クエリ文字列、ログ行、詳細なエラー文を含めません。
