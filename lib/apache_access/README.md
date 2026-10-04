# ApacheAccessReportService

`lib/apache_access` は、Apache のアクセスログを匿名化した件数へ集計し、既存の `MailService` で管理者へ送信する共通ライブラリです。Djangoアプリ、Djangoモデル、migration、専用画面は追加しません。

## `.env` の場所

- Apache固有の設定: リポジトリ直下の `.env`
- `APACHE_ACCESS_LOG_GLOBS`: 任意。未設定なら `/var/log/apache2/access.log*` を使う。ローテーション済み・gzipのログも対象に含む。複数の場所はカンマ区切りで指定する。
- SMTP設定と送信先: 既存の `MailService` を使う。送信できることを事前に確認する。
- GPT要約: 既定では無効です。利用する場合だけ `OPENAI_API_KEY` と `APACHE_ACCESS_GPT_ENABLED=True` をプロジェクトルートの `.env` に設定する。1回のメール送信につきOpenAI APIへの呼び出しは最大1回、出力は250トークンまでです。

## 事前準備（一度だけ、サーバー管理者が実施）

以下は、リポジトリを `/var/www/html/portfolio` に配置し、Web を `www-data` で実行する場合の手順です。

### 1. Apache のログ形式と出力先を確認する

```bash
sudo apache2ctl -S
sudo grep -R "^[[:space:]]*\(LogFormat\|CustomLog\)" /etc/apache2
```

対象が `/var/log/apache2/access.log` とローテート済みの `access.log.*` であり、`LogFormat` が combined 相当であることを確認します。

### 2. Apacheログに読み取り権限を付与して確認する

ブラウザ送信時のWebプロセスは、Apacheログを読み取って集計し、結果をメモリ上でメール送信します。ログや集計結果の保存先は用意しません。最初の `namei` は現在の権限の確認、2つの `setfacl` は `www-data` に読み取り権限だけを付与する設定変更、最後の `test -r` は設定後の確認です。

```bash
sudo namei -l /var/log/apache2/access.log
sudo setfacl -m u:www-data:rx /var/log/apache2
sudo setfacl -m u:www-data:r /var/log/apache2/access.log*
sudo -u www-data test -r /var/log/apache2/access.log && echo OK_web_read || echo NG_web_read
```

`www-data` が対象の `access.log*` を読み取れる状態にします。書き込み権限は付与しません。ローテーション後も読み取りACLが付くように、logrotateの設定を確認します。

### 3. Apache固有の設定を `/var/www/html/portfolio/.env` に追加する

`APACHE_ACCESS_LOG_GLOBS` は任意です。標準の `/var/log/apache2/access.log*` を使う場合は未設定のままにします。ログの場所を変更する場合や、複数の場所を読む場合だけ設定します。

```dotenv
APACHE_ACCESS_LOG_GLOBS=/var/log/apache2/access.log*
```

### 4. Web 側へ変更を反映する

```bash
sudo apache2ctl configtest
sudo systemctl restart apache2
```

`apache2ctl configtest` の期待値は `Syntax OK` です。

## メールを送信する

1. portfolio にスーパーユーザーでログインする。
2. 共通ナビバーの「アクセス集計をメール送信」を1回押す。
3. 元のページに「集計メールを送信しました。」と通知されることを確認する。
4. 固定宛先へ、対象期間、生成時刻、件数を含む HTML・プレーンテキストメールが届くことを確認する。

GPT要約を有効にした場合、同じメールに「GPTによる参考要約」が追加されます。根拠となる匿名化集計値と対象期間をメールで確認し、GPT要約の生成に失敗した場合も機械的な集計メールが届くことを確認します。

送信操作はその時点のログを読み取って集計します。未ログイン、一般ユーザー、スタッフユーザーは送信できません。

## 失敗時の確認順

1. 「Apacheアクセスログが見つかりません」: `APACHE_ACCESS_LOG_GLOBS` と `www-data` のログ読み取り権限を確認する。
2. 集計コマンドが失敗: combined 形式、ログローテーション後のACL、Apacheのエラーログを確認する。
3. メール送信が失敗: 既存の `MailService` のSMTP設定、TLS、送信先、Apacheのエラーログを確認する。
4. 修正後、同じ送信操作を再実行する。
