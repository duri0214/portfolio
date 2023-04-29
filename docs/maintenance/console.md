## local debugging
- `pip install -r requirements.txt`
- `cd mysite`
- `python manage.py runserver`

## server
- `ssh henojiya`
- `systemctl restart apache2`
- `$ git pull`
- `python manage.py makemigrations taxonomy`
- `python manage.py migrate`
- `chown -R ubuntu:ubuntu /var/www/html`
- `cd /var/www/html/portfolio`
- `python /var/www/html/portfolio/mysite/manage.py collectstatic --noinput`

## venv
- `# source /var/www/html/venv/bin/activate`
- `# deactivate`

## ログをダダ流す
> -f オプションは、ファイルを常に読み取り続け、追加された行を表示し続けるオプションです。
- `$ sudo tail -f /var/log/apache2/error.log`
- `$ sudo tail -f /var/log/apache2/access.log`
