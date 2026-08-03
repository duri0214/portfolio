# 図書管理システムをサブドメインで本番公開する

## はじめに

この記事では、既存の VPS で `www.henojiya.net` が動いている状態から、`bookman.henojiya.net` のように別サブドメインを追加して複数のアプリケーションを公開する流れを整理する。

Bookman は、frontend の `bookman_nextjs` と backend の `bookman_backend` に分かれている。
portfolio のように Apache + mod_wsgi だけで画面まで返す構成ではなく、Bookman は Next.js が画面を返し、Apache + mod_wsgi 上の Django REST Framework が API を返す。

そのため、DNS / 公開 Apache / portfolio / Bookman frontend / Bookman backend の責務を分けて考える。

| 対象 | 責務 |
| --- | --- |
| DNS | `www.henojiya.net` と `bookman.henojiya.net` を同じ VPS に到達させる |
| 公開 Apache | `Host` を見て、`www.henojiya.net` は portfolio、`bookman.henojiya.net` は Bookman frontend へ振り分ける |
| portfolio | Apache + mod_wsgi で `www.henojiya.net` の画面を返す |
| Bookman frontend | Next.js で `bookman.henojiya.net` の画面を返し、サーバー側で Bookman backend の DRF API と通信する |
| Bookman backend | Apache + mod_wsgi で `/bookman/api/` 配下の DRF API を localhost 向けに返す |

Bookman のアプリケーション実装メモはこちら。

- [Django-rest-frameworkとNextJSで図書管理システムを作ってみる](https://qiita.com/YoshitakaOkada/items/570c025cf235062649c8)

VPS、Ubuntu、Apache、MySQL、Django の一般セットアップはこちら。

- [CentOSが終わるのでUbuntu24.04に移行する。Python3.12とDjango4とMySQL8のセットアップメモ2026](https://qiita.com/YoshitakaOkada/items/d1e14776040e64cd1434)

## 前提

この記事では次の状態から始める。

- `henojiya.net` はお名前.com で管理している
- DNS はさくらインターネットの `ns1.dns.ne.jp` / `ns2.dns.ne.jp` を使っている
- VPS のグローバルIPは `153.126.200.229`
- portfolio `www.henojiya.net` は同じ VPS で公開済み
- Bookman は同じ VPS 上に2つ目の独自 Web アプリケーションとして配置する
- frontend は [`bookman_nextjs`](https://github.com/duri0214/bookman_nextjs)
- backend は [`bookman_backend`](https://github.com/duri0214/bookman_backend)

実際のドメインやIPは自分の環境に合わせて読み替える。

## 全体像

`www.henojiya.net` と `bookman.henojiya.net` は、どちらも同じ VPS へ到達する。
同じIPに届いたあと、どのアプリケーションへ振り分けるかは Apache の `VirtualHost` で決める。

```mermaid
flowchart TB
  browser[Browser]
  dns[DNS]

  subgraph vps[VPS]
    apache[公開 Apache]
    portfolio[portfolio<br>Apache + mod_wsgi]

    subgraph localhost[localhost]
      nextjs[bookman_nextjs<br>Next.js]
      backendApache[Apache + mod_wsgi<br>127.0.0.1:8000]
      drf[bookman_backend<br>Django REST Framework]
    end
  end

  browser --> dns
  dns --> apache
  apache -->|www.henojiya.net<br>ProxyPass /| portfolio
  apache -->|bookman.henojiya.net<br>ProxyPass /| nextjs
  nextjs -->|BOOKMAN_API_BASE_URL| backendApache
  backendApache --> drf
```

DNS は `www.henojiya.net` と `bookman.henojiya.net` を同じ VPS に到達させるところまでを担当する。
公開 Apache は、届いたリクエストの `Host` を見て、`www.henojiya.net` なら portfolio、`bookman.henojiya.net` なら Bookman frontend へ流す。
portfolio は Apache + mod_wsgi で画面まで返す。
Bookman frontend は Next.js で画面を返し、必要に応じて Next.js の API Route から `BOOKMAN_API_BASE_URL` 配下の Bookman backend へ接続する。
Bookman backend API は外部のエンドポイントとしては公開せず、Next.js のサーバー側から `http://127.0.0.1:8000/bookman/api` に接続する。
この `127.0.0.1:8000` は Bookman backend 用の Apache + mod_wsgi チャンネルで、インターネット側には開かない。
この形にすると、Bookman として外部から見える入口は `bookman.henojiya.net` の Apache `VirtualHost` だけになる。
Django REST Framework API をインターネットから直接触らせないため、公開面が小さくなり、不要な API 露出や CORS / CSRF まわりのリスクを抑えやすい。

## ネームサーバーを設定

ここでやることは、お名前.com で管理している `henojiya.net` と、さくらのVPSで発行されたグローバルIP `153.126.200.229` をひもづけることだ。
1つ目の独自Webアプリケーションを `www.henojiya.net`、2つ目以降の独自Webアプリケーションを `bookman.henojiya.net` として、どちらも同じVPSへ向ける。

名前解決の流れは、ざっくり次のようになる。

1. ブラウザが `bookman.henojiya.net` にアクセスしようとする
2. DNS の仕組みで、`henojiya.net` は `ns1.dns.ne.jp` / `ns2.dns.ne.jp` に聞けばよいと分かる
3. `ns1.dns.ne.jp` / `ns2.dns.ne.jp` に問い合わせる
4. `bookman.henojiya.net` は `153.126.200.229` だと分かる
5. ブラウザが `153.126.200.229` の VPS に接続する

設定は2つ。

### さくらのVPS側の設定

1つ目は、お名前.com 側で `henojiya.net` の問い合わせ先を `ns1.dns.ne.jp` / `ns2.dns.ne.jp` にすること。
`ns1.dns.ne.jp` / `ns2.dns.ne.jp` は、さくらインターネットが用意している DNS サーバーだ。

2つ目は、さくらのVPS側で DNS レコードを設定し、`www` と `bookman` をVPSのIPへ向けること。

DNS レコードの設定画面では、次のように `@` や `www`、`bookman` が並ぶ。

![DNSレコード設定例](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/3f085d89-1aee-47a4-ba8f-3cd8206e46e3.png)

この画面の読み方は次の通り。

- `@` は `henojiya.net` そのものを表す
- `@` は A レコードで VPS のIPへ向ける
- `www` や `bookman` は CNAME で `@` を見るようにしておく
- その結果、`www.henojiya.net` や `bookman.henojiya.net` は `henojiya.net` と同じVPSへ向く

| 種別 | 管理画面で入力する名前 | 値 | 意味 |
|---|---|---|---|
| A | `@` | `153.126.200.229` | `henojiya.net` を VPS のIPへ向ける |
| CNAME | `www` | `@` | `www.henojiya.net` を `henojiya.net` と同じ向き先にする |
| CNAME | `bookman` | `@` | `bookman.henojiya.net` を `henojiya.net` と同じ向き先にする |

ここまでの DNS 設定でできるのは、`www.henojiya.net` や `bookman.henojiya.net` を同じ VPS に到達させるところまで。
同じIPに届いたあと、どの名前をどのアプリやディレクトリに割り当てるかは Apache の `VirtualHost` で設定する。

この画面では「エントリー名」に完全なドメイン名ではなく、サブドメインだけを入力する。
A レコードでも CNAME レコードでも、左側に入れる `@` / `www` / `bookman` はこの「エントリー名」だ。

### さくらのVPS側で設定した DNS の疎通確認

DNS の反映には数分から数時間かかることがある。
この確認は、VPS に入らず PC の PowerShell から実行する。
外から `www.henojiya.net` や `bookman.henojiya.net` がどう見えているかを確認してから、Apache や certbot の設定に進む。
出力は環境によって「サーバー」や「権限のない回答」の表示が変わるため、ここでは見るべき行だけを抜粋する。

```bash:console
# henojiya.net の問い合わせ先が ns1.dns.ne.jp / ns2.dns.ne.jp になっていることを確認
PS C:\Users\yoshi> nslookup -type=NS henojiya.net
henojiya.net nameserver = ns1.dns.ne.jp
henojiya.net nameserver = ns2.dns.ne.jp

# CNAME を確認する
PS C:\Users\yoshi> nslookup -type=CNAME www.henojiya.net
www.henojiya.net canonical name = henojiya.net

# bookman も同じ向き先を見ることを確認
PS C:\Users\yoshi> nslookup -type=CNAME bookman.henojiya.net
bookman.henojiya.net canonical name = henojiya.net
```

PowerShell の `nslookup` では「権限のない回答」と表示されることがあるが、これはエラーではない。
`nameserver`、`canonical name` の行が期待通りなら OK。

DNS の期待値:

- `henojiya.net` の `nameserver` が `ns1.dns.ne.jp` / `ns2.dns.ne.jp` になっている
- `www.henojiya.net` の CNAME が `henojiya.net` を返す
- `bookman.henojiya.net` の CNAME も `henojiya.net` を返す

### curl で疎通確認

```bash:console
# www は HTTPS で正常応答する
PS C:\Users\yoshi> curl.exe -I https://www.henojiya.net
HTTP/1.1 200 OK
Server: Apache
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Type: text/html; charset=utf-8

# bookman は DNS 上は同じVPSに向くが、HTTPS の受け口をまだ用意していないと失敗する
PS C:\Users\yoshi> curl.exe -I https://bookman.henojiya.net
curl: (60) schannel: SNI or certificate check failed: SEC_E_WRONG_PRINCIPAL (0x80090322) - 対象のプリンシパル名が間違っています。
```

curl の期待値:

- `www.henojiya.net` は HTTPS で正常応答する
- `bookman.henojiya.net` は DNS では同じ VPS に届くが、Apache の VirtualHost と証明書をまだ用意していない場合は HTTPS では証明書エラーになる

### トラブルシューティング

うまくいかない場合の切り分け。

- `curl.exe` の結果が想定と違う場合: DNS キャッシュまたは TTL の反映待ち
- `www.henojiya.net` の HTTPS が返らない場合: VPS 側のパケットフィルタ、UFW、Apache の `VirtualHost`、証明書設定を確認
- `bookman.henojiya.net` の HTTPS が証明書エラーになる場合: DNS ではなく、`bookman.henojiya.net` 用の Apache `VirtualHost` と証明書が未設定の状態

## バーチャルホスト

ここでは Apache 側で、ドメイン名ごとの受け口を `VirtualHost` として定義する。
DNS 側で `www.henojiya.net` や `bookman.henojiya.net` がこのサーバーのグローバルIPを向くようにしたあと、この設定の `ServerName` と一致していれば Apache が該当サイトとして処理できる。

`virtual.host.conf` の中に複数の `<VirtualHost *:80>` があっても、Apache はリクエストの `Host` と `ServerName` を見て使うブロックを選ぶ。
そのため、`www.henojiya.net` 側が `DocumentRoot` で portfolio を返し、`bookman.henojiya.net` 側が `ProxyPass /` で Next.js へ流しても衝突しない。

portfolio は Apache + mod_wsgi で画面まで返す一方、Bookman は画面を Next.js に任せ、backend API だけを localhost 側の Apache + mod_wsgi に載せる。
やっていることは、`www` と `bookman` というホスト名の違いで同じIPに届いた通信を別のアプリケーションへ振り分けることだ。
たとえば Next.js を `127.0.0.1:3000` で待ち受けるなら、Apache 側は `bookman.henojiya.net` へのアクセスを Next.js へ流す。

```bash:console
$ sudo vi /etc/apache2/sites-available/virtual.host.conf
```

既存の `virtual.host.conf` に、Bookman frontend 用の `<VirtualHost *:80>` ブロックを追記する。

```conf:/etc/apache2/sites-available/virtual.host.conf
<VirtualHost *:80>
    ServerName bookman.henojiya.net

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/
</VirtualHost>
```

backend API のエンドポイントは外部公開しない。
外向きの Apache `VirtualHost` には backend API 向けの `ProxyPass` / `ProxyPassReverse` を書かず、Next.js だけが BFF を通して localhost の Apache + mod_wsgi に接続する。

`ProxyPass` は `bookman.henojiya.net` に届いたリクエストを Next.js へ転送する設定で、`ProxyPassReverse` は Next.js から返るリダイレクトなどのレスポンスヘッダを外向きのURLに補正する設定だ。
どちらも同じ転送先を書くので似て見えるが、入口の転送と戻りの補正で役割が違う。

`ProxyPass` / `ProxyPassReverse` を使うため、Apache の proxy 関連モジュールを有効化する。

```bash:console
$ sudo a2enmod proxy
$ sudo a2enmod proxy_http
$ sudo a2ensite virtual.host
$ sudo apache2ctl configtest
$ sudo systemctl restart apache2
```

各コマンドの意味は次の通り。

- `a2enmod proxy`: Apache の proxy モジュールを有効化する
- `a2enmod proxy_http`: HTTP 向けの proxy 転送を有効化する
- `a2ensite virtual.host`: `virtual.host.conf` を有効なサイト設定として読み込む
- `apache2ctl configtest`: Apache 設定の構文エラーを確認する
- `systemctl restart apache2`: Apache を再起動して設定を反映する

## backend を配置する

Bookman backend の `bookman_backend` は Django REST Framework API を返す。
この記事では、API の URL は `/bookman/api/` 配下に置く。

portfolio と同じように、本番サーバーでは `/var/www/html/` 配下に `bookman_backend/` と `bookman_nextjs/` を clone する。

```text
/var/www/html/
  portfolio/
  bookman_backend/
  bookman_nextjs/
```

ローカル開発では `~/dev/` 配下に置いていても、本番サーバーでは `portfolio` と同じ階層の `/var/www/html/` 配下に `bookman_backend` と `bookman_nextjs` を配置する想定だ。
サーバー上の配置は次のように確認できる。

```bash:console
$ cd /var/www/html
$ tree -L 1
```

backend 側は、通常の Django アプリケーションとして `.env`、venv、migration、static の設定を整える。
Bookman backend も portfolio と同じく Apache + mod_wsgi に載せる。
ただし、portfolio とはチャンネルを分け、Bookman backend 用に localhost の `127.0.0.1:8000` だけで待ち受ける Apache 設定を作る。
Next.js の BFF から見える API URL は固定しておく。

まず Apache が localhost の 8000 番ポートでも待ち受けるようにする。
`/etc/apache2/ports.conf` は Apache インストール時点で存在する既存ファイルなので、新規作成せずに `Listen 127.0.0.1:8000` だけ追記する。

```bash:console
$ sudo vi /etc/apache2/ports.conf
```

```diff:/etc/apache2/ports.conf
Listen 80
+　Listen 127.0.0.1:8000
```

次に、`virtual.host.conf` に Bookman backend 用の localhost 専用 `VirtualHost` を追記する。

```bash:console
$ sudo vi /etc/apache2/sites-available/virtual.host.conf
```

```conf:/etc/apache2/sites-available/virtual.host.conf
<VirtualHost 127.0.0.1:8000>
    ServerName 127.0.0.1

    WSGIDaemonProcess bookman_backend python-home=/var/www/html/bookman_backend/venv python-path=/var/www/html/bookman_backend
    WSGIProcessGroup bookman_backend
    WSGIScriptAlias / /var/www/html/bookman_backend/config/wsgi.py

    <Directory /var/www/html/bookman_backend/config>
        <Files wsgi.py>
            Require all granted
        </Files>
    </Directory>
</VirtualHost>
```

この `VirtualHost` は `127.0.0.1:8000` だけで待ち受けるため、外部から直接は到達できない。
Next.js の BFF が同じサーバー内から `http://127.0.0.1:8000/bookman/api` に接続し、そこから mod_wsgi 経由で Bookman backend の Django REST Framework が動く。

`mod_wsgi` を使うため、Apache の wsgi モジュールを有効化して設定を反映する。

```bash:console
$ sudo a2enmod wsgi
$ sudo apache2ctl configtest
$ sudo systemctl restart apache2
```

ローカル開発では次のようにしていた。

```env:.env.local
BOOKMAN_API_BASE_URL=http://127.0.0.1:8000/bookman/api
```

本番でも、同じサーバー内だけで閉じるなら次のようにする。

```env:.env.production
BOOKMAN_API_BASE_URL=http://127.0.0.1:8000/bookman/api
```

Bookman の frontend は、Next.js のバックエンド（BFF）が Django REST Framework API と通信する方針にしている。
そのため、`BOOKMAN_API_BASE_URL` は Next.js のサーバー側で読む値として扱う。
backend API を外部公開しないなら、外向きの Apache `VirtualHost` には backend 用の `ProxyPass` / `ProxyPassReverse` は書かない。

## frontend を配置する

Bookman frontend の `bookman_nextjs` は、portfolio と同じ `/var/www/html/` 配下に clone した Next.js アプリケーションだ。
これを build して、`next start` で起動する。
Apache から Next.js へつなぐため、外部に直接公開せず、localhost の別ポートで待ち受ける。

```bash:console
$ cd /var/www/html/bookman_nextjs
$ npm ci
$ npm run build
$ PORT=3000 npm run start
```

この `npm run start` は、起動している間だけ Next.js を動かすコマンドだ。
本番では手動実行のままにせず、systemd などでサービス化して、Ubuntu の再起動後も自動で立ち上がるようにする。
`bookman_nextjs` を pull して更新したときは、`npm ci`、`npm run build` のあとに Next.js のサービスを再起動する。
ここでは Apache の `ProxyPass` が `http://127.0.0.1:3000/` を向いているため、Next.js 側も同じポートで起動する。

## HTTPS 化する

DNS で `bookman.henojiya.net` が同じ VPS へ到達し、Apache の HTTP VirtualHost が有効になったら、certbot で証明書を取得する。

```bash:console
$ sudo certbot --apache -d bookman.henojiya.net
```

証明書取得後は、HTTPS 側の `VirtualHost *:443` にも `ProxyPass` / `ProxyPassReverse` が入っていることを確認する。
certbot が生成または更新した SSL 設定ファイルを確認し、HTTP 側と同じように Bookman の Next.js へ流す。

```conf:/etc/apache2/sites-available/virtual.host-le-ssl.conf
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName bookman.henojiya.net

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/

    SSLCertificateFile /etc/letsencrypt/live/bookman.henojiya.net/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/bookman.henojiya.net/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
</IfModule>
```

反映前に構文チェックを通す。

```bash:console
$ sudo apache2ctl configtest
$ sudo systemctl reload apache2
```

## 確認する

まず PC の PowerShell から HTTPS の入口を確認する。

```bash:console
PS C:\Users\yoshi> curl.exe -I https://bookman.henojiya.net
HTTP/1.1 200 OK
Server: Apache
Content-Type: text/html; charset=utf-8
```

次にブラウザで `https://bookman.henojiya.net` を開き、Bookman の HOME が表示されることを確認する。

frontend と backend の接続確認は、画面から行う。

- `https://bookman.henojiya.net/branch` や `https://bookman.henojiya.net/book` で一覧が表示される
- 一覧が表示されれば、Next.js のサーバー側から Django REST Framework API へ接続できている

もし画面は表示されるが一覧だけ失敗する場合、DNS ではなく `BOOKMAN_API_BASE_URL`、Django 側の URL、Next.js の Route Handler、localhost 側の Apache + mod_wsgi 設定を確認する。

## まとめ

サブドメインを追加しても、DNS がやることは `bookman.henojiya.net` を同じ VPS へ届けるところまでだ。
同じIPへ届いたあと、Bookman に振り分けるのは Apache の `VirtualHost`。
Next.js は画面を返し、Next.js の BFF が localhost の Apache + mod_wsgi 経由で Bookman backend の Django REST Framework API と通信する。

この責務を分けておくと、`www.henojiya.net` の既存 Django サイトと、`bookman.henojiya.net` の Next.js + Django REST Framework アプリを同じ VPS 上で共存させやすい。
