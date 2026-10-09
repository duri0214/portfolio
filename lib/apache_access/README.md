# ApacheAccessTrafficService

`lib/apache_access` は、Apache のアクセスログを日別・応答区分別の匿名化した件数へ集計する共通ライブラリです。ルートの Django アプリ `apache_access/` が、本番の有効なスーパーユーザー向けダッシュボードの実測表示に利用します。表示条件と粒度は [ダッシュボード仕様](../../docs/apache_access_dashboard.md) に記載しています。

## `.env` の場所

- Apache固有の設定: リポジトリ直下の `.env`
- `APACHE_ACCESS_LOG_GLOBS`: 任意。未設定なら `/var/log/apache2/access.log*` を使う。ローテーション済み・gzipのログも対象に含む。複数の場所はカンマ区切りで指定する。

## 事前準備（一度だけ、サーバー管理者が実施）

以下は、リポジトリを `/var/www/html/portfolio` に配置し、Web を `www-data` で実行する場合の手順です。

### 1. Apache のログ形式と出力先を確認する

```bash
sudo apache2ctl -S
sudo grep -R "^[[:space:]]*\(LogFormat\|CustomLog\)" /etc/apache2
```

対象が `/var/log/apache2/access.log` とローテート済みの `access.log.*` であり、`LogFormat` が combined 相当であることを確認します。

### 2. Apacheログに読み取り権限を付与して確認する

ダッシュボードのWebプロセスは、Apacheログを読み取って集計し、画面に表示します。ログや集計結果の保存先は用意しません。最初の `namei` は現在の権限の確認、2つの `setfacl` は `www-data` に読み取り権限だけを付与する設定変更、最後の `test -r` は設定後の確認です。

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

## 失敗時の確認順

1. 「Apacheアクセスログが見つかりません」: `APACHE_ACCESS_LOG_GLOBS` と `www-data` のログ読み取り権限を確認する。
2. ダッシュボードの実測表示が失敗: combined 形式、ログローテーション後のACL、Apacheのエラーログを確認する。
3. 修正後、スーパーユーザーで `/apache_access/` を開き直す。
