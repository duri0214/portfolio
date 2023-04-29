## debugging
- `pip install -r requirements.txt`
- `cd .\mysite\`
- `python manage.py runserver`

## server
- `ssh henojiya`
- `systemctl restart apache2`

## permission
- `chown -R ubuntu:ubuntu /var/www/html`

## path
- `cd /var/www/html/portfolio`
- `$ git pull`

## venv
- `# source /var/www/html/venv311/bin/activate`
- `# deactivate`

## ログをダダ流す
> -f オプションは、ファイルを常に読み取り続け、追加された行を表示し続けるオプションです。
- `$ sudo tail -f /var/log/apache2/error.log`
- `$ sudo tail -f /var/log/apache2/access.log`
