from __future__ import absolute_import, unicode_literals

import os

from celery import Celery

# Djangoのsettingsモジュールをconfig.settingsとして指定
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("portfolio")  # プロジェクト名を使用

# Celery設定をDjangoの設定から読み込む
app.config_from_object("django.conf:settings", namespace="CELERY")

# タスクモジュールを自動的に検出
app.autodiscover_tasks()
