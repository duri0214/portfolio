"""識別子を含まない Apache 集計と送信制限の永続化。"""

from django.db import transaction

from home.models import ApacheAccessReport, ApacheReportDispatch


class ApacheAccessReportRepository:
    """数値だけの集計結果を保存し、最新の一件を取り出す。"""

    @staticmethod
    @transaction.atomic
    def save(period_start, period_end, generated_at, counts):
        """明示した数値項目だけを保存し、古い履歴を削除する。"""
        report = ApacheAccessReport.objects.create(
            period_start=period_start,
            period_end=period_end,
            generated_at=generated_at,
            **counts,
        )
        ApacheReportDispatch.objects.get_or_create(pk=1)
        ApacheAccessReport.objects.exclude(pk=report.pk).delete()
        return report

    @staticmethod
    def latest():
        """直近の集計結果を返す。"""
        return ApacheAccessReport.objects.order_by("-generated_at").first()


class ApacheReportDispatchRepository:
    """送信間隔を複数の Web プロセス間で共有する。"""

    @staticmethod
    def locked_state():
        """呼び出し元のトランザクション内で送信状態の一行をロックする。"""
        return ApacheReportDispatch.objects.select_for_update().get(pk=1)
