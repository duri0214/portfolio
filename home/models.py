from django.db import models


class ApacheAccessReport(models.Model):
    """Apache アクセスログの直近期間について、公開できない識別子を除いた集計値を保持する。

    Attributes:
        period_start: 集計対象の開始日時。
        period_end: 集計対象の終了日時。
        generated_at: 集計結果の生成日時。
        total_requests: 対象期間の総リクエスト件数。
        status_401: 401 の件数。
        status_403: 403 の件数。
        status_404: 404 の件数。
        status_5xx: 5xx の件数。
        failure_sources: 失敗応答を受けた送信元の数。
        top_source_failures: 一つの送信元に集中した失敗応答の最大件数。
        login_requests: portfolio のログイン先へのリクエスト件数。
        top_source_login_requests: 一つの送信元からのログイン先リクエストの最大件数。
        sensitive_path_successes: 要注意パス候補への 2xx 応答件数。
        recent_failures: 期間の後半に発生した失敗応答件数。
        previous_failures: 期間の前半に発生した失敗応答件数。
        malformed_lines: 形式が異なり集計できなかったログ行数。
    """

    period_start = models.DateTimeField(verbose_name="対象期間開始")
    period_end = models.DateTimeField(verbose_name="対象期間終了")
    generated_at = models.DateTimeField(verbose_name="生成日時", db_index=True)
    total_requests = models.PositiveIntegerField(verbose_name="リクエスト総数")
    status_401 = models.PositiveIntegerField(verbose_name="401 件数")
    status_403 = models.PositiveIntegerField(verbose_name="403 件数")
    status_404 = models.PositiveIntegerField(verbose_name="404 件数")
    status_5xx = models.PositiveIntegerField(verbose_name="5xx 件数")
    failure_sources = models.PositiveIntegerField(verbose_name="失敗応答の送信元数")
    top_source_failures = models.PositiveIntegerField(
        verbose_name="送信元別失敗応答の最大件数"
    )
    login_requests = models.PositiveIntegerField(
        verbose_name="ログイン先リクエスト件数"
    )
    top_source_login_requests = models.PositiveIntegerField(
        verbose_name="送信元別ログイン先リクエストの最大件数"
    )
    sensitive_path_successes = models.PositiveIntegerField(
        verbose_name="要注意パス候補への 2xx 件数"
    )
    recent_failures = models.PositiveIntegerField(verbose_name="期間後半の失敗応答件数")
    previous_failures = models.PositiveIntegerField(
        verbose_name="期間前半の失敗応答件数"
    )
    malformed_lines = models.PositiveIntegerField(verbose_name="解析できなかった行数")


class ApacheReportDispatch(models.Model):
    """管理者向け集計メールの最後の送信日時を一行で保持する。

    Attributes:
        last_sent_at: 送信に成功した最後の日時。
    """

    last_sent_at = models.DateTimeField(
        verbose_name="最終送信日時", null=True, blank=True
    )
