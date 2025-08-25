import calendar
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from welfare_services.models import Facility, FacilityAvailability


class Command(BaseCommand):
    """福祉事務所の空き状況データを生成するコマンド

    このコマンドは、開発・テスト用の空き状況ダミーデータを生成します。
    すべての福祉事務所に対して、指定された月数分のデータを生成します。
    """

    help = "福祉事務所の空き状況データを生成します"

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=6,
            help="生成する月数を指定します（デフォルト: 6ヶ月、現在の月を含む）",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="既存の空き状況データを削除してから生成します",
        )

    def handle(self, *args, **options):
        months = options["months"]
        clear = options["clear"]

        # 施設データの確認
        facilities = Facility.objects.all()
        facility_count = facilities.count()

        if facility_count == 0:
            raise CommandError(
                "福祉事務所のデータが存在しません。先に福祉事務所データを作成してください。"
            )

        self.stdout.write(
            f"{facility_count}施設の過去{months}ヶ月分の空き状況データを生成します..."
        )

        # 既存データの削除（オプション）
        if clear:
            self.stdout.write("既存の空き状況データを削除します...")
            FacilityAvailability.objects.all().delete()

        # 現在の日時を取得
        now = timezone.now()

        created_objects = []

        with transaction.atomic():
            # 各施設に対して処理
            for facility in facilities:
                # 指定された月数分のデータを生成
                for i in range(months):
                    # i ヶ月前の年月を計算
                    target_date = now - timedelta(days=30 * i)
                    # 月末日を計算
                    last_day = calendar.monthrange(target_date.year, target_date.month)[
                        1
                    ]
                    month_end_date = date(target_date.year, target_date.month, last_day)

                    # 空き状況をランダムに設定（信号機表示：available=緑, limited=黄, unavailable=赤）
                    # 確率分布: 空きあり(50%), 残りわずか(30%), 空きなし(20%)
                    status_distribution = (
                        ["available"] * 50 + ["limited"] * 30 + ["unavailable"] * 20
                    )
                    status = random.choice(status_distribution)

                    # 空き人数（空き状況に応じて調整）
                    if status == "unavailable":  # 赤（空きなし）
                        available_count = 0
                    elif status == "limited":  # 黄（残りわずか）
                        available_count = random.randint(1, 3)
                    else:  # 緑（空きあり）
                        available_count = random.randint(4, 20)

                    # 既存データがあれば更新、なければ作成
                    obj, created = FacilityAvailability.objects.update_or_create(
                        facility=facility,
                        target_date=month_end_date,
                        defaults={
                            "status": status,
                            "available_count": available_count,
                            "remarks": f"{target_date.year}年{target_date.month}月の空き状況データ（自動生成）",
                        },
                    )

                    created_objects.append(obj)

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(created_objects)}件の空き状況データを生成しました。"
            )
        )
