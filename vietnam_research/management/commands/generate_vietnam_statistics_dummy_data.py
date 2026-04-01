import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from vietnam_research.models import VietnamStatistics


class Command(BaseCommand):
    help = "VietnamStatisticsテーブル用のダミーデータを生成"

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=24,
            help="生成する月数（デフォルト: 24ヶ月）",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="既存のVietnamStatisticsデータを削除してから生成（初期データ用。移行などで既にデータがある場合は実行注意）",
        )

    def handle(self, *args, **options):
        """
        過去Nヶ月分のVietnamStatisticsレコードを自動生成する

        処理内容:
        1. --clearオプションが指定されている場合、既存のVietnamStatisticsデータを削除
        2. 指定された月数分のダミーデータを生成（IIP, CPI）

        データ生成ロジック:
        - IIP (industrial production index): 100を基準にゆるやかに成長
        - CPI (consumer price index): 100を基準にインフレ傾向
        """

        months = options["months"]
        clear_data = options["clear"]

        if clear_data:
            deleted_count = VietnamStatistics.objects.all().count()
            VietnamStatistics.objects.all().delete()
            self.stdout.write(
                f"既存のVietnamStatisticsデータを削除しました（{deleted_count}件）"
            )

        # データの種類
        elements = [
            {"name": "industrial production index", "base": 100.0, "growth": 0.005},
            {"name": "consumer price index", "base": 100.0, "growth": 0.003},
        ]

        # 現在の月から遡って生成
        current_date = datetime.now().replace(day=1)
        records = []

        for element_info in elements:
            element_name = element_info["name"]
            current_value = element_info["base"]

            # 月末日を計算するためのループ
            for m in range(months):
                # mヶ月前の月初
                target_month_first_day = (
                    current_date - timedelta(days=m * 31)
                ).replace(day=1)
                # その月の末日（次の月の1日の1日前）
                if target_month_first_day.month == 12:
                    next_month = datetime(target_month_first_day.year + 1, 1, 1)
                else:
                    next_month = datetime(
                        target_month_first_day.year, target_month_first_day.month + 1, 1
                    )
                period = next_month - timedelta(days=1)

                # ランダムな変動を加えて値を計算
                # インフレ/成長傾向 + ランダムノイズ
                noise = random.uniform(-0.02, 0.02)
                value = current_value * (
                    1 + (element_info["growth"] * (months - m)) + noise
                )

                records.append(
                    VietnamStatistics(
                        element=element_name,
                        period=period.date(),
                        value=round(value, 2),
                    )
                )

        # バルクインサート
        VietnamStatistics.objects.bulk_create(records)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully generated {len(records)} dummy records for VietnamStatistics."
            )
        )
