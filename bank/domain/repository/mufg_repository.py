from django.db import transaction
from bank.models import Bank, MufgDepositCsvRaw
from bank.domain.valueobject.mufg_csv_row import MufgCsvRow


class MufgRepository:
    def __init__(self, bank: Bank):
        self.bank = bank

    def save_rows(self, rows: list[MufgCsvRow]):
        with transaction.atomic():
            for row in rows:
                MufgDepositCsvRaw.objects.get_or_create(
                    bank=self.bank,
                    trade_date=row.trade_date,
                    summary=row.summary,
                    summary_detail=row.summary_detail,
                    payment_amount=row.payment_amount,
                    deposit_amount=row.deposit_amount,
                    balance=row.balance,
                    inout_type=row.inout_type,
                    defaults={
                        "memo": row.memo,
                        "uncollected_flag": row.uncollected_flag,
                    },
                )
