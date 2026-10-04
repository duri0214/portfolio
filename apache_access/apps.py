from django.apps import AppConfig


class ApacheAccessConfig(AppConfig):
    """Apacheアクセス傾向の画面を提供するDjangoアプリ。

    Attributes:
        name: アプリのPythonパッケージ名。
        verbose_name: 管理画面などで使用するアプリ名。
    """

    name = "apache_access"
    verbose_name = "Apache アクセス分析"
