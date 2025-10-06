import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now, localtime

from lib.log_service import LogService
from vietnam_research.models import Industry, Symbol


class Command(BaseCommand):
    help = "Industryテーブル用のダミーデータを生成（デフォルト14日分）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=14,
            help="生成する日数（デフォルト: 14日）",
        )
        parser.add_argument(
            "--start_date",
            type=str,
            help="開始日（YYYY-MM-DD形式）。指定しない場合は今日から--days日前",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="既存のIndustryデータを削除してから生成",
        )

    def handle(self, *args, **options):
        """
        過去N日分のIndustryレコードを自動生成する

        処理内容:
        1. 既存のSymbolデータを参照
        2. --clearオプションが指定されている場合、既存のIndustryデータを削除
        3. 指定された日数分のダミーデータを生成
        4. 各シンボルごとにリアルな価格変動を持つデータを作成

        データ生成ロジック:
        - 基準価格: 10,000 ～ 100,000 の範囲でランダムに設定
        - 日々の変動: 前日比 -5% ～ +5% の範囲で変動
        - open/high/low/closing: 現実的な関係性を保持
        - volume: 100,000 ～ 10,000,000 の範囲で変動
        - marketcap: 100 ～ 10,000 億円の範囲で変動
        - PER: 5 ～ 30 の範囲で変動

        See Also: https://docs.djangoproject.com/en/5.1/howto/custom-management-commands/
        """
        log_service = LogService("./result.log")

        days = options["days"]
        start_date_str = options.get("start_date")
        clear_data = options["clear"]

        # 開始日の決定
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(
                        "開始日の形式が正しくありません。YYYY-MM-DD形式で指定してください。"
                    )
                )
                return
        else:
            # デフォルト: 今日から指定日数前
            start_date = (datetime.now() - timedelta(days=days - 1)).date()

        # 既存データの削除（オプション指定時）
        if clear_data:
            deleted_count = Industry.objects.all().count()
            Industry.objects.all().delete()
            message = f"既存のIndustryデータを削除しました（{deleted_count}件）"
            log_service.write(message)

        # Symbolデータの取得
        symbols = Symbol.objects.select_related("market", "ind_class").all()
        if not symbols.exists():
            message = "Symbolデータが存在しません。先にSymbolデータを登録してください。"
            log_service.write(message)
            return

        message = (
            f"{symbols.count()}件のSymbolに対して{days}日分のダミーデータを生成します"
        )
        log_service.write(message)

        # ダミーデータの生成
        industry_records = []
        for symbol in symbols:
            # 各シンボルごとに基準価格を設定
            base_price = random.uniform(10000, 100000)
            current_price = base_price

            for day_offset in range(days):
                recorded_date = start_date + timedelta(days=day_offset)

                # 前日比で価格を変動させる（-5% ～ +5%）
                price_change_ratio = random.uniform(-0.05, 0.05)
                current_price = current_price * (1 + price_change_ratio)

                # 現実的な価格関係を維持
                # closing_price を基準に open/high/low を決定
                closing_price = round(current_price, 2)

                # 日中の変動幅（-3% ～ +3%）
                daily_volatility = random.uniform(0.01, 0.03)
                price_range = closing_price * daily_volatility

                # open_price: closing の ±2% 以内
                open_price = round(closing_price * random.uniform(0.98, 1.02), 2)

                # high_price: open と closing の高い方 + 変動幅
                high_price = round(
                    max(open_price, closing_price) + price_range * random.uniform(0, 1),
                    2,
                )

                # low_price: open と closing の低い方 - 変動幅
                low_price = round(
                    min(open_price, closing_price) - price_range * random.uniform(0, 1),
                    2,
                )

                # low_price が負にならないように調整
                if low_price < 0:
                    low_price = closing_price * 0.9

                # volume: 100,000 ～ 10,000,000
                volume = round(random.uniform(100000, 10000000), 0)

                # marketcap: 100 ～ 10,000 億円
                marketcap = round(random.uniform(100, 10000), 2)

                # PER: 5 ～ 30（たまに None）
                per = round(random.uniform(5, 30), 2) if random.random() > 0.1 else None

                industry_records.append(
                    Industry(
                        recorded_date=recorded_date,
                        symbol=symbol,
                        open_price=open_price,
                        high_price=high_price,
                        low_price=low_price,
                        closing_price=closing_price,
                        volume=volume,
                        marketcap=marketcap,
                        per=per,
                        created_at=localtime(now()),
                    )
                )

        # バルクインサート
        Industry.objects.bulk_create(industry_records, batch_size=1000)

        final_message = (
            f"ダミーデータの生成が完了しました。"
            f"{len(industry_records)}件のIndustryレコードを作成しました。"
            f"（{symbols.count()}シンボル × {days}日）"
        )
        log_service.write(final_message)
