# CentOSが終わるのでUbuntu24.04に移行する。Python3.12とDjango4とMySQL8のセットアップメモ2026

## はじめに

この記事は、CentOSのサポート終了（EOL）に伴い、OSをUbuntu 24.04 LTSへ移行した際のセットアップ手順をまとめたものです。
2021年の初出から更新を重ねていますが、ここで紹介している構成は現在も本番サーバーで安定稼働しており、実用的なオペレーションマニュアルとして活用しています。
かつてのCentOS環境からのスムーズな移行と、現代的なPython 3.12 + Django 4環境の構築を目指しています。

## Ubuntu 24.04LTS

### OSインストール（さくらのVPS）

さくらのVPSで `Ubuntu 24.04 amd64` を選択してインストールします。
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/4d1f958e-cb49-d901-ef68-bb703900febc.png)

#### ユーザー設定とセキュリティ

Ubuntuでは、デフォルトの一般ユーザー（さくらのVPSでは `ubuntu`）でログインし、必要に応じて `sudo -s` でroot権限に切り替えて操作するのが基本です。

> **なぜ直接rootでログインしないのか？**
> rootユーザーは何でもできてしまう強力な権限を持っているため、万が一パスワードが漏洩したり操作ミスをしたりした際のリスクが非常に大きいです。一般ユーザーでログインし、必要なときだけ `sudo` を使うことで、不用意な破壊操作を防ぎ、セキュリティを向上させられます。

- **管理ユーザーのパスワード**: 「自分で入力したパスワードを使う」を選択し、任意のパスワード（例: `YOUR-COOL-PASSWORD`）を入力します。入力フォームの下に「パスワードの強さ：強力」と表示されるような、複雑なものを設定してください。
- **SSHキー登録**: ここでは「追加済みの公開鍵を使ってインストールする」を選択し、事前にVPS側の管理画面で登録しておいた公開鍵（例: `main pc`）をセットしています。あらかじめ鍵をVPSに保存しておく必要があるため、初めての方や別の方法を取りたい方は、各自の環境に合わせて公開鍵をインストールしてください。
- **スタートアップスクリプト**: `Setup and update` を選択。OSセットアップ時にパッケージの更新などを自動で行ってくれる便利なプリセットです。
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/1b2eccca-4556-3aa1-d364-60de6d56ef57.png)

- 補足: `Setup and update` の設定には「（RedHat系のみ）SELinux を有効化する。」という項目があります。初期値は「有効化しない」なので、そのままになっていることを確認してください。（CentOS 8 時代に SELinux 有効化で大きくハマった教訓）

> 注意（さくらのVPS固有の制約）
> Ubuntu 24.04 を安定してインストール・運用するには、メモリ1GB以上のプランを選択してください。512MBプランではパッケージのインストール失敗やOut of Memory（メモリ不足）によるサービス停止が発生しやすく、実運用には不向きです。根拠: さくらのVPS マニュアル「OSの注意事項」
> https://manual.sakura.ad.jp/vps/support/technical/os-attention.html

#### パケットフィルタの設定

サーバーの安全のため、必要なポートのみを開放します。

- **SSH**: TCP 22（リモートログイン用）
- **Web**: TCP 80/443（HTTP/HTTPS用）
- **FTP**: TCP 20/21（ファイル転送用）


## SSH（Windows/PowerShellからの接続）

> SSH（Secure Shell）とは、暗号化された通信でリモートのUNIX/Linuxマシンに安全に接続するための仕組みです。ID/パスワードや公開鍵で認証し、コマンド実行やファイル転送（SFTP/scp）を安全に行えます。本手順では Windows の PowerShell（OpenSSH クライアント）からサーバへ接続します。

### ※Linuxの記号の意味

Linux初心者は、コンソール上の「$」とか「\#」がよくわかんなかったりする

| 記号 | 意味           |
|:--:|:-------------|
| $  | 一般ユーザ権限で操作中  |
| #  | root権限権限で操作中 |

### ログインチェック（パスワード認証）

以後は Windows の PowerShell（PyCharm のターミナル等）から CUI ベースでログインします。

- 現時点では SSH のみ開放（TCP 22）。HTTP/HTTPS へのリダイレクトやUFW設定はこの後に行います。
- 将来ポートを変更したら `ssh -p <port> ubuntu@<IP>` のように `-p` で指定できます（初期は22）。

手順（PowerShell）

```bash:console
# （Windows）PowerShell から実行
# 初回接続（既定ポート22でSSH）
# ホスト名またはIPを指定（例ではさくらVPSのグローバルIP）
PS C:\Users\yoshi> ssh ubuntu@153.127.13.226
The authenticity of host '153.127.13.226 (153.127.13.226)' can't be established.
ED25519 key fingerprint is SHA256:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '153.127.13.226' (ED25519) to the list of known hosts.
ubuntu@153.127.13.226's password:  # さくらVPSの初期設定で指定した ubuntu のパスワードを入力
```

### 既知鍵の衝突（known_hosts）

既に同一IPで鍵が変わっている場合（OS入れ直し等）は known_hosts の衝突で警告されます。その場合は次のどちらかで解決します。

```bash:console
# （Windows）PowerShell から実行
# 衝突している既存のホストキーを削除（推奨）
PS C:\Users\yoshi> ssh-keygen -R 153.127.13.226

# もしくは known_hosts から該当行を手で削除
PS C:\Users\yoshi> notepad $env:USERPROFILE\.ssh\known_hosts
```

ログイン後の確認（一般ユーザーで入れていることを確認）

```bash:console
$ whoami
ubuntu
$ hostname -I
153.127.13.226
$ pwd
/home/ubuntu
```

これで「一般ユーザー ubuntu でログインできた」ことを PowerShell から機械的に確認できます。

### スーパーユーザーへの切り替え（参考）

基本的には `sudo` を使ってコマンドを実行しますが、root権限に切り替えて作業したい場合は以下のコマンドを使います（すぐに `exit` で戻ることを推奨します）。

```bash:console
# root権限に切り替え
$ sudo -s
[sudo] password for ubuntu:

# 一般ユーザーに戻る
# exit
```

### 公開鍵でログインできるようにする

PCにある公開鍵（例：`id_rsa_henojiya.pub`）をサーバーにアップロードし、以下のコマンドで登録します（まずはパスワード認証で一度ログイン→公開鍵方式へ切り替える流れ）。

まず、公開鍵ファイルがカレントディレクトリにあることを確認します（この例では `/home/ubuntu` に置いた前提）。

```bash:console
# いまの作業場所を確認
$ pwd
/home/ubuntu

# 公開鍵ファイルが存在するか確認
$ ls -l *.pub
-rw-r--r-- 1 ubuntu ubuntu   400 Feb  1 12:34 id_rsa_henojiya.pub
```

```bash:console
# SSH設定ディレクトリの作成と権限設定
$ mkdir ~/.ssh
$ chmod 700 ~/.ssh  # ~/.ssh は 700 である必要あり

# 公開鍵を `authorized_keys` に移動し、権限を設定
$ mv id_rsa_henojiya.pub ~/.ssh/authorized_keys
$ chmod 600 ~/.ssh/authorized_keys  # authorized_keys は 600 である必要あり

> Note:
> - Windows から SCP で転送する場合は PowerShell の `scp`（OpenSSH クライアント）を利用します。
> - 以後は `ssh ubuntu@<IP>` でパスワード入力なしで接続できるはずです（鍵パスフレーズを設定していればその入力は必要）。
```

ターミナルからログインできました！
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/314f4e41-58fc-87b9-de2d-5eb5ab362b47.png)

#### ファイル転送の選択肢（Windows）

> Note: 単発・少量の転送なら `scp` が最短です。GUIでまとめて行う場合は FileZilla（SFTP）が便利です。
> また、さくらのVPSの初期セットアップで「追加済みの公開鍵を使ってインストール」を選択している場合、すでに公開鍵認証でログインできるため、ここでの鍵ファイル転送（.pub のアップロード）は不要なことが多いです（そのままSSH接続へ進んで問題ありません）。

- CUI（最短手）：PowerShell の `scp`
  ```bash:console
  # Windows（PowerShell）から実行（鍵ファイル指定の例）
  PS C:\Users\yoshi> scp -i ~/.ssh/<your_private_key> C:\path\to\localfile ubuntu@153.127.13.226:/home/ubuntu/

  # ディレクトリごと転送する場合（-r）
  PS C:\Users\yoshi> scp -r -i ~/.ssh/<your_private_key> C:\path\to\localdir\ ubuntu@153.127.13.226:/home/ubuntu/localdir/
  ```

- GUI：FileZilla（SFTP）
  - 設定例（サイトマネージャー）
    - ホスト: `153.126.200.229`（例）
    - プロトコル: SFTP – SSH File Transfer Protocol
    - ログオンの種類: 鍵ファイル
    - ユーザー: `ubuntu`
    - ポート: `22`
  - 鍵の登録（初回のみ）
    1. メニューバー: 編集 → 設定 → SFTP を開く
    2. 「鍵ファイルの追加(A)」をクリックし、秘密鍵（例: `C:\Users\yoshi\.ssh\id_rsa` など）を選択
    3. 「FileZilla用に変換して ppk にしますか？」と聞かれたら OK を選択し、例: `id_rsa_filezilla.ppk` のように保存
  - サイトマネージャーで上記 ppk を指定して接続し、`/home/ubuntu` など転送先へドラッグ＆ドロップで配置
  - 参考: もとの記事の FileZilla 手順（鍵の変換含む）: https://qiita.com/YoshitakaOkada/items/a75f664846c8c8bbb1e1#ftp

#### ※ssh 接続で警告が出た場合（known_hosts を更新）

OS を入れ直した直後などは、サーバ側のホスト鍵が変わるため、クライアントに保存されている `known_hosts` と不一致になり、次のような警告が表示されます。これは“以前と別のサーバ鍵になっています”という通知です。

```bash:console
$ ssh example.com
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
```

この場合は、古いホスト鍵の記録を削除してから再接続してください（Windows/PowerShell の例）。

```bash:console
# （Windows）PowerShell から実行
PS C:\Users\yoshi> ssh-keygen -R example.com
PS C:\Users\yoshi> notepad $env:USERPROFILE\.ssh\known_hosts  # 該当行が残っていないか確認・手動削除も可
```

サーバの正当性が確認できたら、再度 `ssh` で接続すると新しいホスト鍵が保存されます。

### よくあるエラーと対処（SSH）

- Permission denied (publickey,password): 鍵が未登録、`authorized_keys` の権限が不正（600以外）や `~/.ssh` の権限が不正（700以外）。上記権限を確認。
- 接続がタイムアウト: UFW やVPS側パケットフィルタで 22/TCP が閉じていないかを確認（`sudo ufw status`）。
- ホスト鍵警告（REMOTE HOST IDENTIFICATION HAS CHANGED!）: OS入れ直し等で鍵が変わった。`ssh-keygen -R <IP>` で該当エントリを削除して再接続。

## Swap 増設

> **Warning:**
> Ubuntu 24.04の標準設定ではスワップ（Swap）が0MBになっています（参照：[さくらのVPSマニュアル](https://manual.sakura.ad.jp/vps/os-packages/ubuntu-24.04.html#swap)）。このままだとメモリ不足でMySQLのインストールに失敗したり、運用中に突然サービスが落ちたりすることがあります。特にメモリが少ないプランでは、スワップの作成は必須です。
>
> 補足: さくらのVPSのスタートアップスクリプト「Setup and update」でも、スワップファイルを自動作成できる場合があります。すでにスワップが作成済みであれば、以下の手順はスキップ可能です。まず `sudo swapon --show` を実行し、`/swapfile` などのエントリが表示されるか確認してください。サイズの調整が必要な場合のみ、本セクションの手順で作り直してください（プランやスクリプト内容により作成サイズは異なることがあります）。

### ステップ1 – システムのスワップ情報を確認

まず、現在スワップが設定されていないことを確認します。

```bash:console
$ sudo swapon --show
（何も出力されなければスワップ領域はありません）

$ free -h
                total        used        free      shared  buff/cache   available
  Mem:           961Mi       889Mi        78Mi       1.5Mi       135Mi        71Mi
  Swap:             0B          0B          0B
```
`Swap: 0B` となっていることがわかります。

### ステップ2 – ディスクの空き容量を確認

スワップファイル（今回は5GB）を作成するための空き容量があるか確認します。

```bash:console
$ df -h
  Filesystem      Size  Used Avail Use% Mounted on
  /dev/vda2        50G  6.0G   41G  13% /
```
`Mounted on` 列が `/` になっている行に注目します。これがルートディレクトリ（システム全体）の空き容量を示しています。`Avail`（空き容量）が5GB以上あることを確認してください。

### ステップ3 – スワップファイルの作成と有効化

今回は5GBのスワップファイルを作成します。

```bash:console
# 5GBのファイルを作成
$ sudo fallocate -l 5G /swapfile

# 権限をrootのみに制限
$ sudo chmod 600 /swapfile

# スワップ領域としてセットアップ
$ sudo mkswap /swapfile

# スワップを有効化
$ sudo swapon /swapfile

# 設定が反映されたか確認
$ sudo swapon --show
NAME      TYPE  SIZE USED PRIO
/swapfile file    5G   0B   -2
```

## Apache2

### インストール

```bash:console
# パッケージの更新を確認
$ sudo apt update

# Apache2と開発用パッケージのインストール
$ sudo apt -y install apache2 apache2-dev

# 動作ステータスを確認
$ sudo systemctl status apache2
```

### 設定
#### security 設定ファイルを編集
```bash:console
$ sudo vi /etc/apache2/conf-enabled/security.conf
```

編集位置（行番号の目安）
- `:set number` 前提
- 12行目: ServerTokens の値を変更（例では12行目）

```diff
# サーバーの情報（バージョン、OSなど）を表示しないように（security.conf の12行目を編集）
- ServerTokens OS
+ ServerTokens Prod
```

#### dir 設定ファイルを編集
```bash:console
$ sudo vi /etc/apache2/mods-enabled/dir.conf
```

編集位置（行番号の目安）
- `:set number` 前提
- 1行目: DirectoryIndex を単一指定に変更

```diff
# ディレクトリ名のみでアクセスできるファイル名を設定（dir.conf の2行目を編集）
- DirectoryIndex index.html index.cgi index.pl index.php index.xhtml index.htm
+ DirectoryIndex index.html
```

#### 000-default 設定ファイルの編集
```bash:console
$ sudo vi /etc/apache2/sites-enabled/000-default.conf
```

編集位置（行番号の目安）
- `:set number` 前提
- 9行目前後: コメントアウトされている ServerName 行を実値で追記
- 9行目直後（ServerName の直下）に HTTPS へ恒久リダイレクトの行をコメントのまま配置（HTTPS 設定が完了するまで）

```diff
# サーバー名を追記（000-default.conf の9行目前後）
- #ServerName www.example.com
+ ServerName www.henojiya.net
```

```conf:/etc/apache2/sites-available/000-default.conf
# httpsの設定が済むまではコメントアウトしておく
# Redirect permanent / https://www.henojiya.net
```

```bash:console
# 設定を反映
$ sudo systemctl restart apache2
```

### 確認

HTTP での応答をコマンドで確認します（スクショではなく機械的に判定できる方法に統一）。

```bash:console
# ヘッダのみ取得してステータスを確認（200 OK を期待）
$ curl -I http://www.henojiya.net
HTTP/1.1 200 OK
Server: Apache/2.x
Content-Type: text/html; charset=iso-8859-1
```

```bash:console
# 本文の先頭を確認（デフォルトの It works! ページなどが返ってくる想定）
$ curl -s http://www.henojiya.net | head -n 10
<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html>
<head>
<title>Apache2 Ubuntu Default Page: It works</title>
```

うまくいかない場合の切り分け（参考）
- `sudo systemctl status apache2` で Apache が起動しているか
- `sudo ufw status` で 80/TCP（Apache）が許可されているか
- `/etc/apache2/sites-enabled/000-default.conf` に `ServerName www.henojiya.net` が入っているか

### ロケールの変更

WSGI アプリを Apache 配下で動かす場合、`www-data` ユーザーのロケールが `C`（ASCII）になっていると、  
ZIP 展開やファイルアップロード時に日本語ファイル名で `UnicodeEncodeError` が発生することがあります。

そのため、Apache の環境変数で UTF-8（`C.UTF-8`）を明示しておくと安全です。  
`C.UTF-8` は locale の生成が不要で、システムを汚さず簡潔に設定できます。

確認（任意）: www-data 視点で UTF-8 になっているか

```bash:console
sudo -u www-data -H bash -lc 'locale'
```

LANG=C.UTF-8 と表示されれば OK。
これで日本語を含む ZIP 展開やファイルアップロードでも UnicodeEncodeError は発生しません。

## バーチャルホスト

いったんパス [もとの記事](https://qiita.com/YoshitakaOkada/items/a75f664846c8c8bbb1e1#%E3%83%90%E3%83%BC%E3%83%81%E3%83%A3%E3%83%AB%E3%83%9B%E3%82%B9%E3%83%88)

```bash:console
$ sudo vi /etc/apache2/sites-available/virtual.host.conf
```

```conf:/etc/apache2/sites-available/virtual.host.conf
<VirtualHost *:80>
    ServerName www.henojiya.net
    DocumentRoot /var/www/html
</VirtualHost>
```


> **Note:**
> 自分メモ（エントリポイントを増やすときはこう書く）
>
> ```
> <VirtualHost *:80>
>     ServerName www.henojiya.net
>     DocumentRoot /var/www/html/portfolio
> </VirtualHost>
> <VirtualHost *:80>
>     ServerName app.henojiya.net
>     DocumentRoot /var/www/html/soil_analysis
> </VirtualHost>
> ```

```bash:console
$ sudo a2ensite virtual.host
$ sudo systemctl restart apache2
```

## ネームサーバーを設定

いったんパス [もとの記事](https://qiita.com/YoshitakaOkada/items/a75f664846c8c8bbb1e1#%E3%83%8D%E3%83%BC%E3%83%A0%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC%E3%82%92%E8%A8%AD%E5%AE%9A)

## HTTPS の準備（443番ポート開放と Apache の SSL 有効化）

このセクションでは、HTTPS 提供に必要な前提作業として UFW で 443/TCP を許可し、Apache 側で SSL サイトとモジュールを有効化します（証明書の取得は後述の「SSL」セクションで実施）。

### ポートをあける

ubuntuの443ポートを開け、ファイアウォールを起動する

```
$ sudo ufw allow in "Apache Full"
$ sudo ufw allow in "OpenSSH"
$ sudo ufw enable
  Command may disrupt existing ssh connections. Proceed with operation (y|n)? y
$ sudo ufw status
  Status: active
  To                         Action      From
  --                         ------      ----
  Apache Full                ALLOW       Anywhere
  OpenSSH                    ALLOW       Anywhere
  Apache Full (v6)           ALLOW       Anywhere (v6)
  OpenSSH (v6)               ALLOW       Anywhere (v6)
```

### サイト設定を有効化する

```bash:console
$ sudo a2ensite default-ssl
  Enabling site default-ssl. // 設定を読み込む
$ sudo a2enmod ssl
  Module setenvif already enabled // apache に SSL モジュールを読み込む
$ sudo systemctl restart apache2 // Apache2 を再起動
```

## SSL

### Let’s Encryptについて

https://letsencrypt.org/ja/docs/rate-limits/

- Let’s Encrypt は、できるだけ多くの人がフェアにサービスを利用できるように、レート制限を設けています
- もしあなたが Let’s Encrypt クライアントの開発やテストを活発に行なっている場合には、本番 API を使用する代わりに、私たちが用意したステージング環境を利用するようにしてください
- 主なレート制限としては、登録ドメインごとの証明書数 (1週間に50個まで) があります
- 登録ドメインとは、一般に言うと、あなたがドメイン名レジストラから購入したドメインの一部のことです。たとえば、`www.example.com` の場合、登録ドメインは `example.com` です。`new.blog.example.co.uk` の場合、登録ドメインは `example.co.uk` です。
- 証明書ごとのドメイン名はできるだけ少ない方がよいです。

### certbot のインストール

```bash:console
# インストール
$ sudo apt -y install certbot python3-certbot-apache
```

### 証明書を取得
```bash:console
# メールアドレスの入力（例）
$ sudo certbot --apache -d www.henojiya.net
Enter email address (used for urgent renewal and security notices)
 (Enter 'c' to cancel): your.name@example.com

# 規約同意（Y の入力例）
Please read the Terms of Service at
https://letsencrypt.org/documents/LE-SA-v1.6-August-18-2025.pdf. You must agree
in order to register with the ACME server. Do you agree?
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
(Y)es/(N)o: Y

# 任意のアンケート。不要なら N（証明書発行には無関係）
Would you be willing to share your email address with the Electronic Frontier Foundation
so they can send you EFF news, campaigns, and ways to support digital freedom?
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
(Y)es/(N)o: N

# 以降は発行〜デプロイの要約（典型的な出力例）
Account registered.
Requesting a certificate for www.henojiya.net

Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/www.henojiya.net/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/www.henojiya.net/privkey.pem
This certificate expires on 2026-05-13.
These files will be updated when the certificate renews.
Certbot has set up a scheduled task to automatically renew this certificate in the background.

Deploying certificate
Successfully deployed certificate for www.henojiya.net to /etc/apache2/sites-available/000-default-le-ssl.conf
Congratulations! You have successfully enabled HTTPS on https://www.henojiya.net
```

> Note:
> - 入力したメールアドレスは証明書更新や重要なお知らせに使われます。後から変更する場合は `sudo certbot register --update-registration --email <new@example.com>`。
> - 非対話で実行したい場合の例（自動化向け）:
>   `sudo certbot --apache -d www.henojiya.net -m your.name@example.com --agree-tos -n`
> - 事前検証はドライランで: `sudo certbot certonly --apache --dry-run`

```bash:console
# 証明書の削除（やり直す場合）
$ sudo certbot delete --cert-name henojiya.net

# 証明書の確認
$ sudo certbot certificates
```

```bash:console
# 証明書の取得テスト（ドライラン）
$ sudo certbot certonly --apache -d www.henojiya.net --dry-run
```

```bash:console
# 証明書の取得（Apache設定は自動で行わない場合）
$ sudo certbot certonly --apache -d www.henojiya.net
```

### FQDN をメモ

`/etc/letsencrypt/live/www.henojiya.net` をメモする（このパスは certbot 実行時に自動作成され、以後の更新でも同じ場所が使われる）。あわせて次のファイルの役割も把握しておく:

- `cert.pem`: サーバ証明書（ドメイン用）
- `privkey.pem`: 秘密鍵（権限は厳格。配布・編集しない）
- `chain.pem`: 中間CA証明書
- `fullchain.pem`: `cert.pem + chain.pem` の連結版（多くのクライアント/設定で推奨）

補足:
- `live` 配下は実体（`/etc/letsencrypt/archive/...`）へのシンボリックリンクで、Certbot が管理する。手動で置換・編集しない。
- `--apache` で自動設定した場合も、`certonly` で証明書だけ取得した場合も、保存先は同じ `live/<FQDN>/`。
- Apache 設定は、例のように `SSLCertificateFile cert.pem` と `SSLCertificateChainFile chain.pem` を分けてもよいし、`SSLCertificateFile fullchain.pem` として `ChainFile` 行を省略する方法でも可。

```bash:console
$ sudo ls /etc/letsencrypt/live/
  README  www.henojiya.net
$ sudo ls /etc/letsencrypt/live/www.henojiya.net
  README  cert.pem  chain.pem  fullchain.pem  privkey.pem
$ sudo openssl x509 -in /etc/letsencrypt/live/www.henojiya.net/fullchain.pem -noout -dates
  notBefore=Aug 29 03:05:54 2021 GMT
  notAfter=Nov 27 03:05:53 2021 GMT
```

### エディタ のデフォルトをviに

```bash:console
$ export EDITOR=vi
```

> **Note:**
> `$ sudo vi /etc/environment`
>
> ```vim:/etc/environment
> VISUAL=/usr/bin/vim
> EDITOR=/usr/bin/vim
> ```
>
> 反映についての補足:
> - `/etc/environment` はシステム全体の環境ファイルで、書式は `KEY=VALUE`（export は不要）。既存の `PATH="..."` の次の行に、以下の2行を追記すれば OK。
>   ```vim:/etc/environment
>   PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin"
>   VISUAL="/usr/bin/vim"
>   EDITOR="/usr/bin/vim"
>   ```
> - 反映は新しいログインセッションから有効になります。設定後は一度ログアウトして再ログイン、または新しいターミナルを開いて確認してください（例: `echo $EDITOR $VISUAL`）。
> - `sudo` 実行時に環境を引き継ぐかは `sudoers` の設定に依存します。必要なら `sudo -E` を使うか、`visudo` で `env_keep += "EDITOR VISUAL"` を検討してください。

### HTTPS 化（Let’s Encrypt 証明書の適用と Apache の設定）

```bash:console
# 設定ファイルの編集
$ sudo vi /etc/apache2/sites-available/default-ssl.conf
```

編集位置（行番号の目安）
- `:set number` 前提

```diff:
31,32行目：取得した証明書に変更
- SSLCertificateFile /etc/ssl/certs/ssl-cert-snakeoil.pem
+ SSLCertificateFile /etc/letsencrypt/live/www.henojiya.net/cert.pem
- SSLCertificateKeyFile /etc/ssl/private/ssl-cert-snakeoil.key
+ SSLCertificateKeyFile /etc/letsencrypt/live/www.henojiya.net/privkey.pem
41行目：
- #SSLCertificateChainFile /etc/apache2/ssl.crt/server-ca.crt
+ SSLCertificateChainFile /etc/letsencrypt/live/www.henojiya.net/chain.pem
```

```bash:console
$ sudo systemctl restart apache2
```

### 確認

```bash:console
# その時点で更新が必要かどうかを確認（必要なら実際に更新される）
$ sudo certbot renew
```

想定される出力の例：
- 更新が不要な場合: `Certificate not yet due for renewal`
- 更新が実行された場合: `Congratulations, all renewals succeeded` などのメッセージ

注意: `--dry-run` は常にテスト用のステージングCAを使った模擬更新で、実際の証明書は更新されません。このセクションでは実際に更新の要否を判定したいので、`--dry-run` は付けません。

### 確認

HTTPS での応答をコマンドで確認します。

```bash:console
# ヘッダのみ取得してステータスを確認（実行例）
$ curl -I https://www.henojiya.net
HTTP/1.1 200 OK
Server: Apache
```

```bash:console
# 本文の先頭を確認（実行例）
$ curl -s https://www.henojiya.net | head -n 10
<title>Apache2 Ubuntu Default Page: It works</title>
```


### ※httpsの設定をしたらApacheが止まる？（結論：Let’s Encrypt のレート制限）

要点だけ：短時間に証明書の取り直しを何度も行うと、Let’s Encrypt のレート制限に達して `certbot` が失敗します。その結果、SSL 設定が中途半端な状態になり、Apache が起動できない／止まったように見えることがあります。

- 代表的なエラー（抜粋）
  - `too many certificates already issued for exact set of domains` など。
  - 公式ドキュメント: https://letsencrypt.org/ja/docs/rate-limits/

どうする？（シンプルな対処）
- まずは待つ（週単位の制限。即時リセットは不可）。
- 検証は本番 API で乱発せず、`--dry-run` による模擬発行で確認する（実ファイルは変更されず、本番のレート制限にも影響しない）。
  - 例: `$ sudo certbot certonly --apache -d www.henojiya.net --dry-run`
- 既存の証明書を再利用する（重複発行を避ける）。
  - `sudo certbot certificates` で確認 → 可能なら `sudo certbot renew`。
- Apache を一時的に HTTP のみで運用しておく（SSL サイトを無効化）。
  - `sudo a2dissite default-ssl; sudo systemctl restart apache2`
- ログで原因確認: `/var/log/letsencrypt/letsencrypt.log`

ポイント：同じ FQDN セットでの短期間の再発行は特に制限にかかりやすいです。手戻り時は「ステージングで検証 → 本番で1回」の順にしましょう。

### http から https へリダイレクト（段階的に有効化）

まずは HTTP の表示確認・Let’s Encrypt の証明書取得・HTTPS の動作確認が終わるまで、リダイレクト行はコメントアウトのままにしておきます。準備が整ったら、次の1行だけをコメント解除（有効化）します。

```bash:console
# 設定ファイルを編集
$ sudo vi /etc/apache2/sites-enabled/000-default.conf
```

```diff:/etc/apache2/sites-enabled/000-default.conf
- # Redirect permanent / https://www.henojiya.net
// （HTTPS 動作確認後にコメントを外す）
+ Redirect permanent / https://www.henojiya.net
```

```bash:console
# 設定を反映
$ sudo systemctl restart apache2
```

以後は HTTP へのアクセスがすべて HTTPS に恒久的に転送されます。

### Let’s Encrypt の証明書更新を自動化するためのスクリプト作成

このセクションでは、Let’s Encrypt の証明書更新用スクリプトを root のホームディレクトリに作成するところまでを行います。定期実行（cron への登録）は後述の「Cron（タスクスケジューラ）」で設定します。

#### スクリプトファイル新規作成
```bash:console
# スクリプトを root のホームに直接作成
$ sudo vi /root/certbot.sh            # ここでスクリプトの内容を書いて保存
```

#### 証明書の更新スクリプト（そのまま転記）
以下は root が実行する前提のスクリプト本文（cron で root 実行）。スクリプト内コマンドに sudo は記述しない。
```bash:certbot.sh
#!/bin/bash
certbot renew

# 更新ログの記録
today=$(date "+%Y/%m/%d %H:%M:%S")
echo "${today} certbot renew" >> /root/certbot_result.log
```

#### 実行権限を付与
```bash:console
$ sudo chmod 755 /root/certbot.sh
```

> Note:
> 定期実行（cron への登録）は、下記の「Cron（タスクスケジューラ）」セクションで設定します。

## MySQL8

### 不要なパッケージの削除

MariaDBなどがインストールされている場合は、事前に削除しておきます。

```bash:console
$ sudo apt purge mariadb-* mysql-*
```

### インストール

```bash:console
# MySQLサーバーのインストール
$ sudo apt -y install mysql-server-8.0

# バージョンの確認
$ mysql --version

# 動作ステータスの確認
$ sudo systemctl status mysql
```

### 初期設定

```bash:console
# セキュリティ設定ウィザードの実行
$ sudo mysql_secure_installation
```

ウィザードでは以下の設定を行います。

- **VALIDATE PASSWORD COMPONENT**: `y` (有効にする)
- **Password Strength**: `2`（HIGH を選択）
- **Remove anonymous users?**: `y` (匿名ユーザーを削除)
- **Disallow root login remotely?**: `y` (rootのリモートログインを禁止)
- **Remove test database?**: `y` (テストDBを削除)
- **Reload privilege tables?**: `y` (設定を即時反映)

### 確認

Ubuntuのデフォルト設定では、rootユーザーは `sudo` を経由してのみログイン可能です。

```bash:console
$ sudo mysql -u root
```

MySQL内での確認：

```sql
-- 文字コードが utf8mb4 になっていることを確認
mysql> status;
```

### データベースとユーザーの作成

```sql
-- データベース作成
CREATE DATABASE portfolio_db DEFAULT CHARACTER SET utf8mb4;

-- ユーザー作成
-- ※ '%' はどこからでも接続可能。セキュリティを高めるなら 'localhost' に限定。
-- 補足: 直前に Password Strength=HIGH を選んだ場合、単純な例（例: 'python123'）は通りません。
--       パスワードジェネレータ等で十分に強いパスワードを作成して指定してください。
CREATE USER 'python'@'%' IDENTIFIED BY 'python123';

-- 権限の付与
GRANT CREATE, DROP, SELECT, UPDATE, INSERT, DELETE, ALTER, REFERENCES, INDEX ON portfolio_db.* TO 'python'@'%';

-- 設定の反映と終了
FLUSH PRIVILEGES;
EXIT;
```

## DBeaver

MySQL Workbench より DBeaver が好きな理由は「GUI で外部キー（FK）を逆追いできる」からです。関連テーブルの参照関係を辿る作業が直感的にできて便利。

「クライアント」は“何かのサービスやサーバに接続して利用する側”の総称です。身近な例:
- Webブラウザ（Chrome/Edge など）: Webサーバのクライアント
- メールアプリ（Outlook/Thunderbird など）: メールサーバのクライアント
- PowerShell や SSH クライアント（ssh.exe）: リモートホスト/SSHサーバのクライアント
- Git クライアント（git コマンドやGUIツール）: Gitサーバ（GitHub/GitLab など）のクライアント
- そして DBeaver は「データベースサーバのクライアント」（= DBクライアント）です。

接続に失敗する場合は、ポートの競合が起きていないかをまず確認してください。
[MySQLのPORTを変える理由](https://qiita.com/YoshitakaOkada/items/691cb598c55df9b6e581#mysql%E3%81%AEport%E3%82%92%E5%A4%89%E3%81%88%E3%82%8D)

### SSHタブ の設定

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/a07041f0-a8d3-b61a-eb5b-88abf9a9fb26.png)

| 入力箇所                  | 入力値                       |
|:----------------------|:--------------------------|
| Host/IP               | 153.126.200.229           |
| Port                  | 22                        |
| User Name             | ubuntu                    |
| Authentication Method | Public Key                |
| Private Key           | （VPSでのログイン時に指定する rsa 秘密鍵） |
| Passphrase            | (ubuntu ユーザーのパスワード）       |

Test tunnel configuration を押して、サーバにつながったことを確認する
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/c2a4bb07-96db-be73-1752-b305851b241c.png)

### 一般タブの設定

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/4518ff31-2896-18b5-efc0-bb4767e77e6b.png)

| 入力箇所        | 入力値                    |
|:------------|:-----------------------|
| Server Host | 127.0.0.1              |
| Port        | 3306                   |
| Database    | portfolio_db           |
| ユーザー名       | python                 |
| パスワード       | （MySQLのrootユーザーのパスワード） |

テスト接続を押して、サーバにつながったことを確認する
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/20f33c30-9288-7b7e-1663-e8e7bcd52920.png)

#### ※Public Key Retrieval is not allowedのエラーが出力される

[DBeaver からローカルのMySQLに接続できない問題への対処法](https://qiita.com/ymzkjpx/items/449c505c50ee17b6e8f9)

## デフォルトページの場所を確認して中身を見てみる

ここまでで「OS のインストール」「Web サーバ（Apache2）のセットアップ」「データベース（MySQL）のセットアップ」が一通り完了しました。Ubuntu では、デフォルトのインデックスページがすでに配置されています。まずはその場所を確認し、ついでに HTML の中身を目視で確認します。

デフォルトの「ドキュメントルート」は `/var/www/html/` です（`/etc/apache2/sites-available/000-default.conf` などで確認できます）。

```console:console
$ sudo vi /var/www/html/index.html
```

`index.html` を開くと、Ubuntu のスタートページ（既定の案内ページ）の HTML が確認できます（CentOS では新規作成でしたが、Ubuntu では最初から用意されています）。

```index:index.html
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1
-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
```

> Note: vi から保存せずに抜けるときは `Shift + ZQ`、保存して抜けるときは `Shift + ZZ`。編集を反映させたくない場合は `Shift + ZQ` で終了しておきましょう。

## Python

### 起動確認

Ubuntu 24.04では標準で Python 3.12 がインストールされています。

```bash:console
# バージョンの確認
$ python3 -V
Python 3.12.3
```

## Git

### バージョン確認

```bash:console
$ git --version
git version 2.43.0
```

### GitHub 連携用の鍵作成

VPS（= 自分のサーバ。ここでは便宜上「me」）が GitHub に安全に接続するには、VPS 側でSSH鍵（秘密鍵/公開鍵ペア）を作成し、その「公開鍵」を GitHub に登録する必要があります。すると、VPS（me）は自分の「秘密鍵」で署名し、GitHub は事前登録された「公開鍵」で検証して、なりすましでないことを確認できます。これにより、パスワードを都度送らずに `git clone`/`git pull` が行えるようになります。

```bash:console
# ユーザー情報を設定（初回のみ）
$ git config --global user.name "<your-name>"
$ git config --global user.email "<your-email@example.com>"

# SSHキー（Ed25519）の作成
$ ssh-keygen -t ed25519 -C "<your-email@example.com>"
# ※保存場所やパスフレーズを聞かれますが、基本はEnter連打（パスフレーズなし）でOKです。

# 公開鍵の中身を表示してコピーする
$ cat ~/.ssh/id_ed25519.pub
```

コピーした内容を GitHub の `Settings > SSH and GPG keys > New SSH key` に登録します。

### 接続確認

```bash:console
$ ssh -T git@github.com
# 「Hi username! You've successfully authenticated...」と出れば成功です。
```

> Note:
> - このコマンドは「SSH鍵でGitHubに認証できるか」をテストする疎通確認です。必須手順ではありませんが、SSH方式（例: `git@github.com:owner/repo.git`）で `git clone/pull/push` を行う予定なら、事前に一度実行しておくと原因切り分けが容易になります。
> - 失敗する典型例と対処：
>   - 公開鍵がGitHubに未登録 → GitHubの Settings > SSH and GPG keys に `~/.ssh/id_ed25519.pub` 等を登録
>   - 別名の鍵を使っている → `~/.ssh/config` に `Host github.com` `IdentityFile ~/.ssh/<your_key>` を設定
>   - パーミッション不備 → `chmod 700 ~/.ssh; chmod 600 ~/.ssh/*`
>   - 22番ポートが閉じている → `~/.ssh/config` で `Hostname ssh.github.com` `Port 443` を指定

## プロジェクトの Clone

既存のプロジェクトを GitHub から Clone して構築する場合の手順です。

```bash:console
# ディレクトリの所有権を変更（ubuntuユーザーで操作可能にする）
$ sudo chown -R ubuntu:ubuntu /var/www/html

# Cloneの実行
$ cd /var/www/html
$ git clone git@github.com:<your-username>/portfolio.git
```

## venv（仮想環境）の準備

```bash:console
# venvパッケージのインストール
$ sudo apt -y install python3.12-venv

# クローンしたプロジェクトのルートへ移動
$ cd /var/www/html/portfolio

# 仮想環境の作成
$ python3 -m venv venv

# 仮想環境の有効化
$ source venv/bin/activate

# 仮想環境内での確認
(venv) $ python -V
Python 3.12.3

# 仮想環境の無効化（必要に応じて）
(venv) $ deactivate
```

## 依存パッケージのインストール

```bash:console
# MySQLクライアントのビルドに必要なライブラリをインストール
$ sudo apt update
$ sudo apt install -y libmysqlclient-dev pkg-config python3-dev

# 仮想環境の有効化とパッケージインストール
$ source venv/bin/activate
(venv) $ pip install -r requirements.txt
```

## 環境ファイル（.env）の配置を確認

`/var/www/html/portfolio` 配下には、アプリごとに複数の `.env` が必要になる場合があります。どこに何を置くべきかを把握するため、ひな型の `*.env.example` を全検索して一覧表示します（このリストに基づいて、同じ場所へ `.env` をFTP/SCPで配置）。

```bash:console
$ cd /var/www/html/portfolio

# 相対パスの一覧（配置先の把握用）
$ find . -type f -name "*.env.example" | sort
```

> Note:
> - 表示された `./<path>/.env.example` ごとに、同ディレクトリに `.env` を用意します（中身は `.env.example` を参考に必要な値へ編集）。
> - `.env` は Git 管理外が前提のため、FTP/SCP でサーバへ配置してください。
> - 機微情報（パスワード・APIキー）は必ず安全な手段で共有・保管します。

> **Note:**
> `.env` などの環境設定ファイルは Git 管理外にしている場合が多いため、FTP 等で個別にアップロードするのを忘れないようにしてください。

## mod_wsgi

Apache と Python を連携させるためのモジュール `mod_wsgi` を設定します。

### インストール

```bash:console
# 仮想環境内でインストール
(venv) $ pip install mod_wsgi
```

### 設定情報の確認

後の手順で Apache の設定ファイルに記述するためのパスを確認します。

```bash:console
# 前提：プロジェクトのルートへ移動（例）
$ cd /var/www/html/portfolio

# mod_wsgi本体のパスを確認
$ find venv -name "mod_wsgi*.so"
# 期待値例: venv/lib/python3.12/site-packages/mod_wsgi/server/mod_wsgi-py312.cpython-312-x86_64-linux-gnu.so

# Python Home (仮想環境) のパスを確認（WSGIDaemonProcess の python-home に指定する値）
# 方法A: find でプロジェクト配下から venv を特定（推奨）
$ find /var/www/html/portfolio -maxdepth 2 -type d -name 'venv'
# 期待値例: /var/www/html/portfolio/venv

# 方法B: 仮想環境を有効化して Python 側で prefix を確認
$ source venv/bin/activate
(venv) $ python -c 'import sys; print(sys.prefix)'
# 期待値例: /var/www/html/portfolio/venv
(venv) $ deactivate
```

### Apache 設定ファイルの編集（APT 方式に統一）

> 方針の明確化（LoadModule 方式からの移行）
> - かつては VirtualHost（サイト設定）内に `LoadModule wsgi_module ...` を直書きする「LoadModule 方式」で運用していたが、以後は Ubuntu/Debian 標準のパッケージ管理である APT を用いた「APT 方式」に統一する。
> - 「APT 方式」とは、Apache および mod_wsgi を OS 公式パッケージ（例: `libapache2-mod-wsgi-py3`）で導入し、`a2enmod`/`a2dismod` と `/etc/apache2/mods-available/* → mods-enabled/*` による標準のモジュール管理に従う運用を指す。
> - 対比: `pip install mod_wsgi` で仮想環境（venv）内に導入し、`LoadModule` をサイト設定に直書きして独自の `.so` を読み込む方法は、本ドキュメントでは「ソース/venv 方式」または「LoadModule 方式」と呼ぶ。
> - なぜ移行するか（利点）: 依存関係と更新を APT に一元化できる／ディレクトリや設定レイアウトが標準に揃う／`LoadModule` の二重読み込み事故を避けやすい。
> - 注意点: Apache や Python のバージョンは基本的に配布パッケージ提供版に合わせる前提（必要に応じてバックポートや PPA を検討）。

```bash:console
# 設定ファイルの編集
$ sudo vi /etc/apache2/sites-available/000-default.conf
```

開いたら、ファイルの最後に、以下の設定ブロック（WSGIScriptAlias〜最後の </Directory> まで）をそのまま追記してください。
すでに同等設定がある場合は重複しないように調整します（順序や値は既存を優先）。

```conf:/etc/apache2/sites-available/000-default.conf
# 方針: APT 方式（`libapache2-mod-wsgi-py3` + `a2enmod wsgi`）に従う。
# LoadModule は mods-enabled/wsgi.load に任せ、このファイルには書かない。

WSGIScriptAlias / /var/www/html/portfolio/config/wsgi.py
WSGIDaemonProcess wsgi_app python-home=/var/www/html/portfolio/venv python-path=/var/www/html/portfolio
WSGIProcessGroup wsgi_app
WSGISocketPrefix /var/run/wsgi
WSGIApplicationGroup %{GLOBAL}

# 静的ファイル（CSS/JS/画像）の設定
Alias /static/ /var/www/html/portfolio/static/
<Directory /var/www/html/portfolio/static>
    Require all granted
    Options -Indexes
</Directory>

# プロジェクトディレクトリへのアクセス許可
<Directory /var/www/html/portfolio/config>
    <Files wsgi.py>
        Require all granted
    </Files>
</Directory>
```

```bash:console
# 設定を反映
$ sudo systemctl restart apache2
```

> **各項目の意味:**
> - **WSGIScriptAlias**: URL と `wsgi.py` の紐付け設定。
> - **WSGIDaemonProcess**: Python 仮想環境のパスを指定し、デーモンモードで実行します（ここでは APT 版 mod_wsgi と venv を組み合わせています）。
> - **WSGIProcessGroup**: デーモンプロセスをグループ化します。
> - **WSGIApplicationGroup %{GLOBAL}**: numpy の `Interpreter change detected` 回避、拡張モジュールとの相性対策。

> Note: `numpy` 等で「Interpreter change detected」が出るケースの対策は、上記の
> `WSGIApplicationGroup %{GLOBAL}` です。本ブロックに既に含めていますが、
> 既存環境にこの行が無い場合のみ、同一行を1カ所だけ追記してください（重複不要）。

#### APT 方式での前提と確認

APT 方式では、`LoadModule` の記述は Apache 標準のモジュール管理に任せます（`/etc/apache2/mods-available/wsgi.load` → `a2enmod wsgi` → `/etc/apache2/mods-enabled/wsgi.load`）。

確認コマンド:

```bash:console
$ dpkg -l | grep libapache2-mod-wsgi-py3
$ ls -l /usr/lib/apache2/modules/mod_wsgi.so
$ apache2ctl -M | grep wsgi
```

`apache2ctl -M` に `wsgi_module (shared)` が出ていれば有効です。`AH01574: module wsgi_module is already loaded, skipping` が出る場合は、`000-default.conf` に重複する `LoadModule` 行が無いか確認し、削除してください（APT 方式では不要）。

> 補足（何を確認するコマンドか）
> - `$ apache2ctl -M | grep -i wsgi` … Apache に mod_wsgi が“読み込まれている（Enabled）”ことを確認する最小チェック。これで `wsgi_module (shared)` が見えれば mod_wsgi は有効です。
> - `$ dpkg -l | grep libapache2-mod-wsgi-py3` … APT 版の mod_wsgi パッケージが“インストール済みか”を確認（入っていない場合は `a2enmod wsgi` 以前の問題）。
> - `$ ls -l /usr/lib/apache2/modules/mod_wsgi.so` … `.so` の実体/リンク先を確認（壊れたリンクや想定外のバージョン差し替えを検知）。
> まずは1行目（最小確認）だけで十分。問題がある場合に、下2行で導入状況や配置を深掘りします。


### ※numpy: Interpreter change detected への対応（補足）

Django で `numpy` を使う場合、`mod_wsgi` 経由で `Interpreter change detected` が発生することがあります。
対策は「`WSGIApplicationGroup %{GLOBAL}` を有効にする」ことです。本対応は上の設定ブロック
（上位セクション「Apache 設定ファイルの編集（APT 方式に統一）」の設定ブロック）に既に統合済みです。未導入の既存環境のみ、同一行を1カ所だけ追記してください。

### エラーが発生した場合は

Apacheのエラーログを確認することで、原因を特定できます。

```bash:console
$ sudo tail -f /var/log/apache2/error.log
```

## Cron（タスクスケジューラ）

CronはWindowsでいうタスクスケジューラだ。決まった時間に決まったコマンドを実行してくれる。CentOSとの操作の差はないみたい。
[Cronの設定](https://kapibara-sos.net/archives/595)

### 定期実行するプログラムの作成

```bash:console
# 作業用ディレクトリに移動
$ cd /var/www/html

# テスト用スクリプトの作成
$ vi hello-cron.py
```

```python:hello-cron.py
import codecs
from datetime import datetime

log_file_path = '/var/www/html/hello-cron.log'
txt = datetime.now().strftime("%Y/%m/%d %H:%M:%S") + ' hello-cron.py'
with codecs.open(log_file_path, 'a', 'utf-8') as f:
    f.writelines('\n' + txt)
```

```bash:console
# 実行テスト
$ python3 hello-cron.py

# ログの確認
$ cat hello-cron.log
```

### Cron の設定

```bash:console
# crontabの編集
$ crontab -e
```

設定例：
10分ごとに実行する場合は `*/10 * * * *` と記述します。仮想環境のPythonをフルパスで指定するのがポイントです。

```vim:crontab
# 10分ごとに実行
*/10 * * * * /var/www/html/portfolio/venv/bin/python /var/www/html/hello-cron.py

# 毎月1日の0:00に証明書を更新
0 0 1 * * /home/ubuntu/certbot.sh

# バッチ処理の例（自分用メモ）
0 0 1 * * /root/certbot.sh
0 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py daily_import_from_vietkabu
5 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py daily_import_from_sbi
6 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py daily_import_market_data
15 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py daily_industry_chart_and_uptrend
20 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py daily_industry_stacked_bar_chart
25 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py daily_download_edinet
30 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py weather_fetch_forecast
35 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py weather_fetch_warning
40 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py collectstatic --noinput
45 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py update_sector_rotation
50 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py fetch_usa_rss
51 18 * * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py update_macro_indicators
15 18 1 * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py monthly_fao_food_balance_chart
15 19 1 * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py monthly_cleanup_linebot_engine
20 19 1 * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py monthly_update_msci_weights
25 19 1 * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py monthly_update_historical_assets
30 19 1 * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py monthly_update_nasdaq100_list

# ※相手先サーバ（ベトナム）の証明書がうまくなくて実行できない
20 18 1 * * /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py monthly_vietnam_statistics
```

### その他

ここから下は、必要に応じて参照してください。


> **Warning:**
> バッチファイルには実行権限を忘れずに与える
>
> ```bash:console
> cd /var/www/html/portfolio/vietnam_research/management/commands
> chmod +x daily_import_from_vietkabu.py
> chmod +x daily_import_from_sbi.py
> chmod +x daily_import_market_data.py
> chmod +x daily_industry_chart_and_uptrend.py
> chmod +x daily_industry_stacked_bar_chart.py
> chmod +x monthly_fao_food_balance_chart.py
> chmod +x monthly_vietnam_statistics.py
> ls -l
>
> cd /var/www/html/portfolio/soil_analysis/management/commands
> chmod +x weather_fetch_forecast.py
> chmod +x weather_fetch_warning.py
> ls -l
>
> cd /var/www/html/portfolio/linebot_engine/management/commands
> chmod +x monthly_cleanup_linebot_engine.py
> ls -l
>
> cd /var/www/html/portfolio/home/management/commands
> chmod +x monthly_cleanup_home.py
> ls -l
> ```

```bash:console
$ vi hello-cron.log
```

```bash:console
2020/03/28 02:18:26 hello-cron.py
2020/03/28 02:28:26 hello-cron.py
```

```bash:console
$ sudo chown -R ubuntu:ubuntu /var/www/html
```


> **Warning:**
> - cronで失敗するのは、staticを置き換える（python manage.py collectstatic）ときに置き換え先のpermissionがrootになってて上書きミスってるのとかがありそう。権限をまとめてubuntu扱いに、を忘れずに


> **Warning:**
> cronを試し打ちしようとしたらこんなエラーが出たよ
>
> ```bash:console
> (venv) $ /var/www/html/portfolio/venv/bin/python /var/www/html/portfolio/manage.py daily_import_from_vietkabu
> Traceback (most recent call last): File "/var/www/html/portfolio/manage.py", line 15, in <module> ..."/var/www/html/portfolio/venv/lib/python3.12/site-packages/fastkml/__init__.py", line 28, in <module> from pkg_resources import
> DistributionNotFound ModuleNotFoundError: No module named 'pkg_resources'
> ```
>
> ```bash:console
> pip install -U setuptools
> ```

#### Reset（※必要に応じて）

1. ~~まず各appディレクトリの `migrations` ディレクトリを消してまわります~~
2. `db` を消します（＝portfolio_db）
3. `db` を作ります

##### ※migrationsは .gitignore に含めないで！

上記1番に取り消し線を引いた理由
なんかしらねーけどCIでのテストが通らなくて困っていた![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/63e47f99-d81e-80ce-1dbc-c1ba8045455b.png)


> **Warning:**
> ぼく「もしかしてだけど `migrations` フォルダを `.ignore` すると `python manage.py test` で影響ある？」
> gpt「はい、`.gitignore` に `migrations` フォルダを含めていると、`python manage.py test` に影響を与える可能性があります。特に以下のような影響があります」
>
> ###### 影響
>
> マイグレーションファイルが存在しない:
> `migrations` フォルダ内にはマイグレーションファイル（例えば `0001_initial.py` など）が含まれています。これらのファイルはデータベースのスキーマを管理し、Djangoが適用するマイグレーションの履歴を保持します。もしこのフォルダが `.gitignore` されていて、CI環境などでマイグレーションファイルが存在しない場合、テスト実行時にデータベーススキーマが適用されず、エラーになります。
>
> テスト用データベースにスキーマが反映されない:
> テスト用データベースは、マイグレーションを適用することでスキーマが反映されますが、マイグレーションファイルがないと、Djangoは適切にデータベーススキーマを作成できません。その結果、`auth_user` のようなテーブルが存在せず、`django.db.utils.OperationalError` が発生する可能性があります。
>
> ###### 解決策
>
> `migrations` フォルダを `.gitignore` から外す: 開発やテスト環境で正しく動作するために、`migrations` フォルダはバージョン管理システムに含めておくことが推奨されます。これにより、`CI/CD` 環境でも正しいマイグレーションが適用され、テスト用データベースが正しく構築されます。
>
> ぼく「ほんとだ　解決したわ。。。」
> ぼく「じゃあdjangoの `test` コマンドはマイグレーションファイルを作成せずに既存のマイグレーションファイルを利用するということね？（ローカルでうまくいくのは無視されるファイルが存在するから）」
>
> gpt「はい、その通りです。`python manage.py test` コマンドは、**既存のマイグレーションファイルを利用してテスト環境にデータベースをセットアップします。**」
>
> gpt「つまり、`migrations` フォルダにあるマイグレーションファイルがテストの際に使われるため、もしそのフォルダが `.gitignore` などで無視されていたり、CI環境で存在していないと、マイグレーションが実行されずにエラーが発生する可能性があります。」
>
> gpt「一方で、ローカル環境では `.gitignore` によって無視されるファイルが存在しているので、マイグレーションが正常に動作しているため、問題なくテストが通るということですね。」


> **Note:**
> なんで `migrations` フォルダを `.gitignore` したの？
> ぼく「モデルなんてゴロゴロ変わるからさ！」

#### migrationとcreatesuperuser

```bash:console
$ cd /var/www/html/portfolio
$ python manage.py makemigrations vietnam_research gmarker shopping linebot_engine warehouse taxonomy soil_analysis securities
$ python3 manage.py migrate
```


> **Warning:**
> なんか migrationで止まるケースがあって、そのときに root で実行すると通るみたいな状況が発生している　ほんとに root 権限が解決しているのかは不明。
>
> いや、一般ユーザでmigrationできた。メモリでVPSが落ちているようだから止まったらサーバーを強制再起動だな

```console:Console（管理ユーザーも消えるので、必要な場合はもう一度作ります）
$ python3 manage.py createsuperuser
  Email address:
  Password:
  Password (again):
  Superuser created successfully.
```

### 確認

djangoがシステム的に作ったテーブルと、アプリケーションを作っていればアプリケーション名が先頭についたテーブルが作成される（赤枠）
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/a6915c45-1195-4801-691e-afb51d3353ca.png)

## MySQLデータ のインポート

https://qiita.com/YoshitakaOkada/items/45ebdc00cc923d970638
リストアのみならこれ
※自分メモ（ローカルからVPSのインポートは事故るから、マイグレーション済んだらsuperuserを手で追加したあと、ダンプからDrop・Create命令を除外したものを作って）

https://qiita.com/shy_azusa/items/9f6ba519cfda626db52b

```console:console
vi /etc/my.cnf
```

```text:/etc/my.cnf
[mysqld]
wait_timeout            = 86400
max_allowed_packet      = 1G
innodb_buffer_pool_size = 1G
```

```console:console
service mysql restart
```

```console:console(Ubuntu)SCPした場所にcdしてから
# mysql -u root -p
mysql> use portfolio_db
mysql> source mysql_dump.sql
```

## 権限（wsgi が読める権限を確保）

mod_wsgi（Apache の wsgi モジュール）がアプリを読み込めるよう、最低限の読み取り権限を付与しておく。所有者は `ubuntu:ubuntu` のままで構わないが、Apache 実行ユーザー（`www-data`）が以下を満たす必要がある。

- `WSGIScriptAlias` で指定した `wsgi.py` を含むディレクトリに「実行 (x)」があり辿れること
- `wsgi.py` 本体を「読み取り (r)」できること
- `python-path` で指定したプロジェクト配下の `.py` も読めること
- 静的ファイル配下（例: `/var/www/html/portfolio/static`）にも `x`/`r` があること

典型的には、ディレクトリ 755、ファイル 644 にしておけば wsgi が読める。

```bash:console
# wsgi が読める最小権限（ディレクトリ=755, ファイル=644）を一括で付与
$ sudo find /var/www/html/portfolio -type d -exec chmod 755 {} +
$ sudo find /var/www/html/portfolio -type f -exec chmod 644 {} +
```

さんざん `root` のままディレクトリとか作りまくってると `access denied` や `permission error` になっていることがあるので注意。特に `/var/www/html/portfolio/config/wsgi.py` と、その親ディレクトリに `x` 権限が無いと mod_wsgi がアプリを読み込めず 500 になる。

## FTP

いったんパス [もとの記事](https://qiita.com/YoshitakaOkada/items/a75f664846c8c8bbb1e1#ftp)

## Django のバッチをつくる

https://qiita.com/YoshitakaOkada/items/3b5da2d77e54d833dac6

## Django で自動テストをする

バッチのテストもこっち

https://qiita.com/YoshitakaOkada/items/2709dfb13dc209025480

## Ubuntuのmatplotlib、日本語問題

https://qiita.com/Atommy1999/items/db533fc8b69a5afe29d2

```console:console
$ sudo apt install -y fonts-ipafont
$ sudo ls ~/.cache/matplotlib/
$ sudo rm ~/.cache/matplotlib/fontlist-v330.json
$ sudo fc-cache -fv
$ sudo fc-list | grep -i ipa
  /usr/share/fonts/opentype/ipafont-mincho/ipam.ttf: IPAMincho,IPA明朝:style=Regular
  /usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf: IPAPGothic,IPA Pゴシック:style=Regular
  /usr/share/fonts/opentype/ipafont-mincho/ipamp.ttf: IPAPMincho,IPA P明朝:style=Regular
  /usr/share/fonts/opentype/ipafont-gothic/ipag.ttf: IPAGothic,IPAゴシック:style=Regular
  /usr/share/fonts/truetype/fonts-japanese-mincho.ttf: IPAMincho,IPA明朝:style=Regular
  /usr/share/fonts/truetype/fonts-japanese-gothic.ttf: IPAGothic,IPAゴシック:style=Regular
```

```python:vietnam_research/management/commands/daily_industry_stacked_bar_chart.py
font_path = '/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf'
if Path.exists(Path(font_path).resolve()):
    # for ubuntu jp font
    plt.legend(loc='upper left', labels=df.columns, prop={"family": "IPAMincho"})
else:
    plt.legend(loc='upper left', labels=df.columns, prop={"family": "MS Gothic"})
```

windows にも入れちゃったほうがいいや

https://qiita.com/Maron_T/items/1565449fbaccfddb1ec3

## PdfMiner

- SBI topics で使用している
- pdfminer.six へライブラリを変更したら解決した

```console:console
pip install pdfminer.six
```

## CI環境 を整える

https://qiita.com/YoshitakaOkada/items/1dc5dd643ba84ebcc74f

## Django プロジェクトを新規で始める場合

### Django インストール

```console:console（venvをアクティベートしてからね）
# source /var/www/html/portfolio/venv/bin/activate
# pip3 install django
# django-admin --version
  4.0.2
```

### pip list

```console:console
# pip list
  Package       Version
  ------------- -------
  asgiref       3.4.1
  Django        4.0.2
  mod-wsgi      4.9.0
  pip           20.0.2
  pkg-resources 0.0.0
  pytz          2021.1
  setuptools    44.0.0
  sqlparse      0.4.1
```

### よく使うライブラリ

```console:console
# pip3 install wheel numpy pandas sqlalchemy beautifulsoup4 matplotlib pillow lxml stripe
```

```console:console（権限をまとめてubuntu扱いに）
# chown -R ubuntu:ubuntu /var/www/html
```

### わかりやすいプロジェクト構成

新規作成時のみ

- ベースディレクトリ名と設定ディレクトリ名が同じでややこしい
- テンプレートと静的ファイルがアプリケーションごとにバラバラに配置されてしまう

これらを解決する。ベースディレクトリを作成したあとにベースディレクトリの下に移動し、設定ディレクトリ名と `.` を指定する

```console:console
$ mkdir mypage
$ cd mypage
$ django-admin startproject config .
$ python manage.py startapp hoge
$ python manage.py runserver
```

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/02b75dc9-1055-b6e8-1140-71808801e460.png)

### settings.py

ALLOWED_HOSTS（許可するドメイン）を編集する

```console:console
# vi /var/www/html/portfolio/config/settings.py
```

```diff:/var/www/html/portfolio/config/settings.py
- ALLOWED_HOSTS = []
+ ALLOWED_HOSTS = ['.henojiya.net', '127.0.0.1', 'localhost', '153.126.200.229']
```

loggerを有効にする（loggingモジュールでコンソールに情報が出せるようになる）

```py:/var/www/html/portfolio/config/settings.py（一番下に追加）
    :
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

```

### mysqlclient

```
(venv)# apt -y install build-essential libssl1.1 libssl1.1=1.1.1f-1ubuntu2 libssl-dev libmysqlclient-dev
(venv)# pip3 install mysqlclient environ

```

```diff:/var/www/html/portfolio/config/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
DATABASES = {
    'default': {
-       'ENGINE': 'django.db.backends.sqlite3',
-       'NAME': BASE_DIR / 'db.sqlite3',
+       'ENGINE': 'django.db.backends.mysql',
+       'NAME': 'portfolio_db',
+       'USER': 'python',
+       'PASSWORD': 'python123',
    }
}
```

```console:console
# service apache2 restart
```

## Django

### ログイン機能

セットアップのタイミング的にここに書いておくけどアプリケーション作るのに慣れてからやること。ログイン機能は、ログイン機能としてのアプリケーションを別個につくるのがベスト・プラクティスだ。

### Reset（※必要に応じて）

1. まず各appディレクトリの `migrations` ディレクトリを消してまわります
2. dbを消します（＝portfolio_db）
3. db を作ります

### startapp

[Django でUserモデルのカスタマイズ](https://narito.ninja/blog/detail/39/)

```console:console
# cd /var/www/html/portfolio
# python3 manage.py startapp register
```

```py:/var/www/html/portfolio/register/models.py
from django.db import models
from django.core.mail import send_mail
from django.contrib.auth.models import PermissionsMixin, UserManager
from django.contrib.auth.base_user import AbstractBaseUser
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone


class CustomUserManager(UserManager):
    """ユーザーマネージャー"""
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """カスタムユーザーモデル."""

    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)

    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_(
            'Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = CustomUserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in
        between."""
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

    @property
    def username(self):
        """username属性のゲッター

        他アプリケーションが、username属性にアクセスした場合に備えて定義
        メールアドレスを返す
        """
        return self.email
```

```diff:/var/www/html/portfolio/config/settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
+    'register.apps.RegisterConfig',
]
```

```diff:/var/www/html/portfolio/config/settings.py（最下段に追記）
+ # login
+ LOGIN_URL = 'register:login'
+ LOGIN_REDIRECT_URL = 'vnm:index'  #ログイン後にリダイレクトしたい先
+ LOGOUT_REDIRECT_URL = "vnm:index" #ログアウト後にリダイレクトしたい先
+ AUTH_USER_MODEL = 'register.User'
```

```console:/var/www/html/portfolio/register
# mkdir -p templates/register
# vi templates/register/base.html
```

```html:/var/www/html/portfolio/register/templates/register/base.html
{% load static %}
<!DOCTYPE html>
<html lang="ja">
<head>
    <!-- Global site tag (gtag.js) - Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=UA-43097095-9"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'UA-43097095-9');
    </script>

    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">
    <title>VNMビューア</title>

    <!-- css -->
    <link rel="stylesheet" href="{% static 'register/css/reset.css' %}">
    <link rel="stylesheet" href="{% static 'register/css/index.css' %}">

    <!-- font -->
    <link href="https://fonts.googleapis.com/css?family=Sawarabi+Gothic" rel="stylesheet">
    <!-- fontawesome -->
    <link href="https://use.fontawesome.com/releases/v5.6.1/css/all.css" rel="stylesheet">

    <!-- favicon -->
    <link rel="shortcut icon" href="{% static 'register/images/c_r.ico' %}">

</head>
<body>
    <!-- nav -->
    <h1></h1>

    <div id="main">
        {% block content %}{% endblock %}
    </div>

    <footer>
        <p>© 2019 henojiya. / <a href="https://github.com/duri0214" target="_blank">github portfolio</a></p>
    </footer>

</body>
</html>
```

```py:/var/www/html/portfolio/register/views.py
"""views.py"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.sites.shortcuts import get_current_site
from django.core.signing import BadSignature, SignatureExpired, loads, dumps
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.views import generic
from .forms import UserCreateForm

# signup
class UserCreate(generic.CreateView):
    """ユーザー仮登録"""
    template_name = 'register/user_create.html'
    form_class = UserCreateForm

    def form_valid(self, form):
        """仮登録と本登録用メールの発行."""
        # 仮登録と本登録の切り替えは、is_active属性を使うと簡単です。
        # 退会処理も、is_activeをFalseにするだけにしておくと捗ります。
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        # アクティベーションURLの送付
        current_site = get_current_site(self.request)
        domain = current_site.domain
        context = {
            'protocol': self.request.scheme,
            'domain': domain,
            'token': dumps(user.pk),
            'user': user,
        }
        folder = settings.BASE_DIR + '/register/templates/register/mail_template/'
        subject = render_to_string(folder + 'subject.txt', context)
        message = render_to_string(folder + 'message.txt', context)

        user.email_user(subject, message)
        return redirect('register:user_create_done')


class UserCreateDone(generic.TemplateView):
    """ユーザー仮登録したよ"""
    template_name = 'register/user_create_done.html'


class UserCreateComplete(generic.TemplateView):
    """メール内URLアクセス後のユーザー本登録"""
    template_name = 'register/user_create_complete.html'
    timeout_seconds = getattr(settings, 'ACTIVATION_TIMEOUT_SECONDS', 60*60*24)  # デフォルトでは1日以内

    def get(self, request, *args, **kwargs):
        """tokenが正しければ本登録."""
        token = kwargs.get('token')
        try:
            user_pk = loads(token, max_age=self.timeout_seconds)

        # 期限切れ
        except SignatureExpired:
            return HttpResponseBadRequest()

        # tokenが間違っている
        except BadSignature:
            return HttpResponseBadRequest()

        # tokenは問題なし
        else:
            try:
                user = get_user_model().objects.get(pk=user_pk)
            except get_user_model().DoesNotExist:
                return HttpResponseBadRequest()
            else:
                if not user.is_active:
                    # 問題なければ本登録とする
                    user.is_active = True
                    user.save()
                    return super().get(request, **kwargs)

        return HttpResponseBadRequest()


class Login(LoginView):
    """ログインページ"""
    template_name = 'register/login.html'
```

```py:/var/www/html/portfolio/register/forms.py
"""forms.py"""
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

class UserCreateForm(UserCreationForm):
    """ユーザー登録用フォーム"""

    class Meta:
        model = get_user_model()
        fields = ('email',)

    def clean_email(self):
        """clean_email"""
        email = self.cleaned_data['email']
        get_user_model().objects.filter(email=email, is_active=False).delete()
        return email
```

```html:/var/www/html/portfolio/register/templates/register/login.html
{% extends "register/base.html" %}
{% block content %}
<div class="card col-md-6">
    <div class="card-body">
        <form action="{% url 'register:login' %}" method="POST">
            {{ form.non_field_errors }}
            {% for field in form %}
                {{ field }}
                {{ field.errors }}
                <hr>
            {% endfor %}
            <button type="submit" class="btn btn-success btn-lg btn-block" >ログイン</button>
            <input type="hidden" name="next" value="{{ next }}" />
            {% csrf_token %}
        </form>
    </div>
</div>
<div class="">
    <div class="card-body">
        <a href="{% url 'register:user_create' %}" class="" >会員登録</a>
    </div>
</div>
{% endblock %}
```

```py:/var/www/html/portfolio/register/urls.py
"""urls.py"""
from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView

app_name = 'register'

urlpatterns = [
    path('login/', LoginView.as_view(template_name='register/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('user_create/', views.UserCreate.as_view(), name='user_create'),
    path('user_create/done', views.UserCreateDone.as_view(), name='user_create_done'),
    path('user_create/complete/<str:token>/', views.UserCreateComplete.as_view(), name='user_create_complete'),
]
```

### admin管理画面 にテーブルを追加表示する

実体としてどれだけテーブルがあろうと、管理画面には表示されないので設定する必要がある。
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/9e514f1c-8f7e-50e4-bbcc-a0e5e69d398c.png)

```diff_python:shopping/admin.py
from django.contrib import admin
+ from .models import Staff, Store, Products, BuyingHistory

# Register your models here.
+ admin.site.register(Staff)
+ admin.site.register(Store)
+ admin.site.register(Products)
+ admin.site.register(BuyingHistory)
```

表示された！アプリケーションごとにやる必要があるね
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/6e19c219-c165-496a-459c-8433a503b848.png)

### Django アプリケーションの新規作成

```console:console
# cd /var/www/html/portfolio
# python3 manage.py startapp vietnam_research
```

### 非公開情報を.envに移す（GitGuardian対策）

https://qiita.com/YoshitakaOkada/items/570c025cf235062649c8#%E9%9D%9E%E5%85%AC%E9%96%8B%E6%83%85%E5%A0%B1%E3%82%92env%E3%81%AB%E7%A7%BB%E3%81%99gitguardian%E5%AF%BE%E7%AD%96

### view 作成

```console:console
# vi vietnam_research/views.py
```

```py:views.py
from django.http import HttpResponse

def index(request):
    return HttpResponse("Hello, world.")
```

### settings.py

```console:console
# vi config/settings.py
```

```py:settings.py（追記）
INSTALLED_APPS = [
    ...,
    'vietnam_research.apps.VietnamResearchConfig'
]
```

### httpd.conf（wsgi.conf）

staticディレクトリ配下は開放。
※あくまで DEBUG = True のときの設定です。慣れてきて DEBUG = False にするときは [こっち](https://qiita.com/YoshitakaOkada/items/a75f664846c8c8bbb1e1#debug%E3%82%92false%E3%81%AB%E3%81%97%E3%81%A6%E3%81%BF%E3%81%A6) を参照

> Note: 上位セクション「Apache 設定ファイルの編集（APT 方式に統一）」の設定ブロックで `Alias /static/ ...` は既に設定済みです。以下は DEBUG=False 運用時の意味付けのみで、追加入力は不要です（重複設定は行わない）。

### vietnam_research/urls.py を編集

URLの紐づけをロケットアニメのHelloWorldから変えるために、urls.py を新規作成する（作る場所は「vietnam_research」フォルダ）。便宜上「子供のurls.py」と呼ぶことがある。「urls.py」には「s」[をつけろよデコ助野郎](https://www.google.com/search?q=%E3%81%95%E3%82%93%E3%82%92%E3%81%A4%E3%81%91%E3%82%8D%E3%82%88%E3%83%87%E3%82%B3%E5%8A%A9%E9%87%8E%E9%83%8E&oq=%E3%81%95%E3%82%93%E3%82%92&aqs=chrome.4.69i57j0l5.3335j1j7&sourceid=chrome&ie=UTF-8)。
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/a3776ef4-6833-dd36-32d8-51b38e4e4c3e.png)

```console:vietnam_research/urls.py
from django.urls import path

# 現在のフォルダの「views.py」を import する！さっき "Hello, world." したやつ！
from . import views

# views.py には「index」という関数を作りましたね！それを呼んでます
urlpatterns = [
    path('', views.index, name='index'),
]
```

### urls.py（共通Configのほう）

NTTの配電盤みたいなイメージね。便宜上「親のurls.py」と呼ぶことがある。（※この英語部分もよく読むと実はさっき子供のurls.pyに書いたようなことをやれって書いてあったりする）

```py:urls.py（共通Configのほう）
"""portfolio URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('vietnam_research/', include('vietnam_research.urls')),
    path('admin/', admin.site.urls),
]
```

```console:console
# systemctl restart apache2
```

### HelloWorld!

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/e14a98d5-2632-56b4-cb5d-f6fbe89f1c94.png)
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/02de1763-fdff-4377-f5bc-860f81a3907d.png)

### model.py

ここはデータベースとテーブルの話だからね。好きにやってちょうだい

```py:model.py
"""このファイル内に、必要なテーブルがすべて定義されます"""
from django.db import models

class Industry(models.Model):
    """
    viet-kabuで取得できる業種つき個社情報
    closing_price: 終値（千ドン）
    volume: 出来高（株）
    trade_price_of_a_day: 売買代金（千ドン）
    marketcap: 時価総額（億円）
    """
    market_code = models.CharField(max_length=4)
    symbol = models.CharField(max_length=10)
    company_name = models.CharField(max_length=50)
    industry1 = models.CharField(max_length=10)
    industry2 = models.CharField(max_length=20)
    open_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    high_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    low_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    closing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    volume = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    trade_price_of_a_day = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    marketcap = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    per = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pub_date = models.DateField()
```

### migrations

`makemigrations` は台帳登録みたいなイメージ

```console:console
# python3 manage.py makemigrations vietnam_research
```

### migrate

migrateは「実効」みたいなイメージ

```console:console
# python3 manage.py migrate
  Operations to perform:
    Apply all migrations: admin, auth, contenttypes, sessions
  Running migrations:
    Applying contenttypes.0001_initial... OK
    Applying auth.0001_initial... OK
    Applying admin.0001_initial... OK
    Applying admin.0002_logentry_remove_auto_add... OK
    Applying admin.0003_logentry_add_action_flag_choices... OK
    Applying contenttypes.0002_remove_content_type_name... OK
    Applying auth.0002_alter_permission_name_max_length... OK
    Applying auth.0003_alter_user_email_max_length... OK
    Applying auth.0004_alter_user_username_opts... OK
    Applying auth.0005_alter_user_last_login_null... OK
    Applying auth.0006_require_contenttypes_0002... OK
    Applying auth.0007_alter_validators_add_error_messages... OK
    Applying auth.0008_alter_user_username_max_length... OK
    Applying auth.0009_alter_user_last_name_max_length... OK
    Applying auth.0010_alter_group_name_max_length... OK
    Applying auth.0011_update_proxy_permissions... OK
    Applying sessions.0001_initial... OK
```

### アプリケーションとして認識させる

<B>（このステップ忘れるべからず）</B>
このsettingでアプリケーションとして認識させることで、index.htmlを開きにいったときの「templates/{アプリケーション名}/index.html」を自動的に識別して読みにいってくれる。
[DjangoでTemplateDoesNotExistと言われたら](https://udomomo.hatenablog.com/entry/2018/08/14/234153)

> 「各アプリケーションの配下にあるtemplatesディレクトリ」を探索するということは、アプリケーションと認識されていなければ探索されないということだ。
> 今回はそもそもここに原因があった。settings.pyのINSTALLED_APPSにmyappを登録するのを忘れていた。

INSTALLED_APPS に設定を追加するんだが、、え？VietnamResearchConfigに覚えがないって？
そうなんだよ、アプリケーションフォルダ（test_chartjs）配下にある、「apps.py」を開いてみると書いてあるんだよね。わかりにくいなぁこれ。

```diff:/var/www/html/portfolio/config/settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
+   'test_chartjs.apps.VietnamResearchConfig',
]
```

### templates ディレクトリを作成

最初に、アプリケーションフォルダの中に「templates」フォルダを作成。さらにその中に、（Djangoのテンプレート読み込みルールに則り）アプリケーションフォルダと同じ名前のフォルダを作成してから index.html というファイルを作成する。
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/3f874441-08e8-7f34-a2ac-f32267109540.png)

つまり、テンプレートは「<B>vietnam_research</B>/templates/<B>vietnam_research</B>/index.html」に書く必要がある。「テンプレートフォルダのなかにアプリケーション名がある」というの自体はほかのWeb言語にもあったような気がする？:thinking:
これは文化的なもので「名前空間」という意味合いに過ぎない。
<B>「templates」には「s」</B>[をつけろよデコ助野郎](https://www.google.com/search?q=%E3%81%95%E3%82%93%E3%82%92%E3%81%A4%E3%81%91%E3%82%8D%E3%82%88%E3%83%87%E3%82%B3%E5%8A%A9%E9%87%8E%E9%83%8E&oq=%E3%81%95%E3%82%93%E3%82%92&aqs=chrome.4.69i57j0l5.3335j1j7&sourceid=chrome&ie=UTF-8)。

### テンプレートを編集

vscodeのhtmlファイル上で「!」って入力すると、vscodeのちょっとした機能でこのテンプレートが出てくる. すごい

```html:index.html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>vietnam_research</title>
</head>
<body>
    <h1>vietnam_research</h1>
</body>
</html>
```

### static ディレクトリを作成

- static（黄色の四角）
- static/vietnam_research（オレンジ）
- static/vietnam_research/js

などのフォルダやファイルは、手で作る必要があります。
（templateと同じ階層にstaticをつくります）
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/96d52716-6da2-5156-1bc5-3e775a3bc697.png)

- htmlの最初に {% load static %} を忘れるな！
- javascript を読み込むときのパスは {% static 'vietnam_research/js/script.js' %} だ
- このフォルダの「指定方法」と「そしてどうなる」を脳筋になるまで繰り返して感覚をつかめ！

### Google Analytics
`<head>` タグの一番最初に取り付ける

```html:index.html
<!-- Global site tag (gtag.js) - Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=UA-43097095-9"></script>
<script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'UA-43097095-9');
</script>
```

### index.html

```html:index.html
{% load static %}
<!DOCTYPE html>
<html lang="ja">
    <head>
        <!-- Global site tag (gtag.js) - Google Analytics -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=UA-43097095-9"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'UA-43097095-9');
        </script>

        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>shopping</title>

        <!-- css -->
        <link rel="stylesheet" href="{% static 'vietnam_research/css/reset.css' %}">
        <link rel="stylesheet" href="{% static 'vietnam_research/css/index.css' %}">
        <!-- favicon -->
        <link rel="icon" href="{% static 'vietnam_research/c_v.ico' %}">

        <!-- javascript -->
        <script src="{% static 'vietnam_research/js/script.js' %}"></script>

        <!-- font -->
        <link href="https://fonts.googleapis.com/css?family=Sawarabi+Gothic" rel="stylesheet">
        <!-- fontawesome -->
        <link href="https://use.fontawesome.com/releases/v5.6.1/css/all.css" rel="stylesheet">

        <!-- for ajax -->
        <script>let myurl = {"base": "{% url 'vnm:index' %}"}</script>

    </head>

    <body>
        <h1>vietnam_research</h1>
    </body>
</html>
```

### views.pyがテンプレートへ向けて置換をかけて返却する流れを作る

```py:vietnam_research/views.py
"""views.py"""
from django.shortcuts import render

def index(request):
    """いわばhtmlのページ単位の構成物です"""
    # htmlとして返却します
    return render(request, 'vietnam_research/index.html')
```

### ローカル環境でのテスト

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/311aaef8-c54c-5c18-2913-d660a68e3ad7.png)

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/6950deb6-93cc-97af-cc12-c2df17e84948.png)

### フォームでのファイルアップロードを実装する

いやー [stackoverflowで質問しても](https://stackoverflow.com/questions/61180565/django3-file-upload-default-permission-is-420) 回答つかなくて困った困った。settings.pyの MEDIA の役割がわかってなかったんだよね。

```py:settings.py
# これの追記で permissionerror 回避を確認ok
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
```

上記の settings.py の追記に加えて、下記のように models.py で upload_to='shopping/ にすると、[example.com]/media/shopping/xxx.jpg と保存されるようになる

```py:models.py
class Products(models.Model):
    """商品"""
    code = models.CharField('商品コード', max_length=200)
    name = models.CharField('商品名', max_length=200)
    price = models.IntegerField('金額', default=0)
    description = models.TextField('説明')
    picture = models.ImageField('商品写真', upload_to='shopping/')
```

```py:views.py（あとはフォームの内容を料理するだけや）
class UploadSingleView(FormView):
    """UploadSingleView"""
    form_class = SingleRegistrationForm
    success_url = reverse_lazy('shp:index')

    def form_valid(self, form):
        # prepare
        code = form.cleaned_data.get('code')
        Products.objects.filter(code=code).delete()
        # save
        form.save()
        # delete if file is exists as same.
        orgname, ext = os.path.splitext(form.cleaned_data["picture"].name)
        mvfilepath = settings.BASE_DIR + '/shopping/static/shopping/img/' + code + ext.lower()
        if os.path.exists(mvfilepath):
            os.remove(mvfilepath)
        # move file as rename
        uploadfilepath = settings.BASE_DIR + '/media/shopping/' + orgname + ext.lower()
        os.rename(uploadfilepath, mvfilepath)
        return super().form_valid(form)
```

### DEBUGをFalseにしてみて？

[公式：本番環境における静的ファイルの配信](https://docs.djangoproject.com/ja/3.0/howto/static-files/deployment/#serving-static-files-in-production)
DEBUGをTrueにしているあいだは気にすることはないが、本番環境にしようとしてDEBUGをFalseにすると /static/ (settings.pyのSTATIC_URL)は各アプリケーション内のstaticディレクトリを読みにいきません。
（非効率であったり、セキュリティ上の理由らしい）

```py:settings.py（デバッグモードをオフ！）
DEBUG = False
```

```settings.py（STATIC_URLのあたりが良いよ）
パス参考：/var/www/html/portfolio/static/
STATIC_ROOT = os.path.join(BASE_DIR, "static")
```

```consols:consols（/var/www/html/portfolio/staticに静的ファイルをコピーする）
# python3 manage.py collectstatic
# chown -R ubuntu:ubuntu /var/www/html
```

```console:console
# systemctl restart apache2
```
