"""Apache アクセスログから管理者向けの集計結果を生成する。"""

from datetime import timedelta
from glob import glob
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from home.domain.repository.apache_access import ApacheAccessReportRepository
from home.domain.service.apache_access import aggregate_access_logs


class Command(BaseCommand):
    """定期実行ユーザーだけが Apache ログを読み、匿名化した集計を DB に保存する。"""

    help = "Apache combined アクセスログの直近24時間を数値だけに集計する"

    def handle(self, *args, **options):
        """設定済みのログを読み、失敗時は既存の集計を更新しない。"""
        patterns = settings.APACHE_ACCESS_LOG_GLOBS
        paths = sorted({Path(name) for pattern in patterns for name in glob(pattern)})
        if not paths:
            raise CommandError(
                "Apache アクセスログが見つかりません。設定と権限を確認してください。"
            )

        generated_at = timezone.now()
        period_end = generated_at
        period_start = period_end - timedelta(hours=24)
        try:
            counts = aggregate_access_logs(paths, period_start, period_end)
        except (OSError, EOFError) as error:
            raise CommandError(
                f"Apache アクセスログを読み取れませんでした: {error}"
            ) from error
        if counts["total_requests"] == 0 and counts["malformed_lines"]:
            raise CommandError(
                "Apache ログ形式を解析できません。combined 形式か確認してください。"
            )

        ApacheAccessReportRepository.save(
            period_start, period_end, generated_at, counts
        )
        self.stdout.write(self.style.SUCCESS("Apache アクセス集計を保存しました。"))
