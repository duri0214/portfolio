import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from bank.models import Bank, MufgDepositCsvRaw


class Command(BaseCommand):
    help = "MufgDepositCsvRaw のダミーデータを生成します"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=10, help="生成するデータ件数 (デフォルト: 10)"
        )

    def handle(self, *args, **options):
        count = options["count"]

        # MUFG 銀行マスタの取得または作成
        bank, created = Bank.objects.get_or_create(
            financial_code="0005",
            defaults={"name": "三菱UFJ銀行", "remark": "ダミーデータ用"},
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"銀行マスタを作成しました: {bank.name}")
            )

        summaries = ["振込", "利息", "給与", "公共料金", "ATM出金", "カード決済"]
        summary_details = [
            "アマゾン",
            "ガスダイ",
            "スイドウダイ",
            "デンキダイ",
            "コンビニ",
            "スーパー",
        ]

        start_date = date.today() - timedelta(days=365)
        current_balance = 1000000  # 初期残高 100万円

        dummy_records = []
        for i in range(count):
            trade_date = start_date + timedelta(
                days=i * (365 // count) if count > 0 else 0
            )
            summary = random.choice(summaries)
            summary_detail = random.choice(summary_details)

            # 入金か出金かをランダムに決定
            is_deposit = random.choice([True, False])

            payment_amount = None
            deposit_amount = None

            if is_deposit:
                deposit_amount = random.randint(1000, 500000)
                current_balance += deposit_amount
            else:
                payment_amount = random.randint(1000, 200000)
                current_balance -= payment_amount

            inout_type = "入金" if is_deposit else "支払い"

            record = MufgDepositCsvRaw(
                bank=bank,
                trade_date=trade_date,
                summary=summary,
                summary_detail=summary_detail,
                payment_amount=payment_amount,
                deposit_amount=deposit_amount,
                balance=current_balance,
                memo="Dummy Data",
                uncollected_flag="0",
                inout_type=inout_type,
            )
            dummy_records.append(record)

        MufgDepositCsvRaw.objects.bulk_create(dummy_records)

        self.stdout.write(
            self.style.SUCCESS(
                f"{count} 件の MufgDepositCsvRaw ダミーデータを生成しました"
            )
        )
