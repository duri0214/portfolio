# Server Permission Management Skill

## 概要
Ubuntu + Apache (mod_wsgi) + Django 環境において、Web サーバー実行ユーザー (`www-data`) とバッチ実行/デプロイユーザー (`ubuntu`) が共存してファイルを読み書き・削除できるようにするための権限管理手法を定義します。

## 発生しやすい問題
1. **PermissionError (バッチ実行時)**: Apache が生成したメディアファイルを、`ubuntu` ユーザーが実行する Django 管理コマンド（バッチ）で削除・上書きしようとすると発生。
2. **Not Found (DEBUG=False 時)**: Apache の設定に `Alias /media/` が不足しているため、動的に生成された画像が表示されない。
3. **git clean 失敗**: `www-data` が生成した一時ファイルやログを `ubuntu` ユーザーが削除できず、デプロイ時の環境クリーンアップが止まる。

## 解決策の三段構え

### 1. OS レベルの所有権と基本権限
プロジェクトディレクトリ以下の所有権を `ubuntu:www-data` に設定し、グループ書き込み権限を付与します。

```bash
sudo chown -R ubuntu:www-data /var/www/html/portfolio
sudo find /var/www/html/portfolio -type d -exec chmod 775 {} +
sudo find /var/www/html/portfolio -type f -exec chmod 664 {} +
```

### 2. ACL (Access Control List) による権限継承
`chmod` だけでは新しく作成されたファイルに権限が反映されないため、ディレクトリに ACL を設定して、新規ファイルに自動で `ubuntu` と `www-data` の両方に rwx 権限を継承させます。

```bash
# ACL ツールのインストール
sudo apt update && sudo apt install acl -y

# media ディレクトリ等、相互に書き込みが必要な場所に設定
sudo setfacl -R -d -m u:ubuntu:rwx /var/www/html/portfolio/media
sudo setfacl -R -d -m g:www-data:rwx /var/www/html/portfolio/media
sudo setfacl -R -d -m o::rx /var/www/html/portfolio/media
```

### 3. Django レベルのパーミッション設定
Django 自体もファイルを作成する際に、グループ書き込み権限を明示的に付与するように `settings.py` に記述します。

```python:config/settings.py
# Apache(www-data)が生成したメディアファイルをubuntuユーザーが削除・上書きできるように
# グループ書き込み権限(664/775)を明示的に付与します。
FILE_UPLOAD_PERMISSIONS = 0o664
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o775
```

## チェックリスト
- [ ] `Alias /media/ /var/www/html/portfolio/media/` が Apache 設定に含まれているか？
- [ ] `Alias /static/ /var/www/html/portfolio/static/` が Apache 設定に含まれているか？
- [ ] `media/` 以下のファイル所有者が `ubuntu` または `www-data` で、かつグループに書き込み権限があるか？
- [ ] `getfacl <dir>` を実行して、権限が適切に設定されているか？
