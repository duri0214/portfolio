from django.db import transaction
from bank.models import Bank, MufgDepositCsvRaw
from bank.domain.valueobject.mufg_csv_row import MufgCsvRow


class MufgRepository:
    def __init__(self, bank: Bank):
        self.bank = bank

    def save_rows(self, rows: list[MufgCsvRow]) -> int:
        """
        行を保存する。1件でも重複があれば、そのファイル全体の保存を中止する。
        :param rows: 保存する行リスト
        :return: 新規作成件数
        :raises ValueError: 重複データが見つかった場合
        """
        with transaction.atomic():
            for row in rows:
                # 重複チェック
                exists = MufgDepositCsvRaw.objects.filter(
                    bank=self.bank,
                    trade_date=row.trade_date,
                    summary=row.summary,
                    summary_detail=row.summary_detail,
                    payment_amount=row.payment_amount,
                    deposit_amount=row.deposit_amount,
                    balance=row.balance,
                    inout_type=row.inout_type,
                ).exists()

                if exists:
                    raise ValueError(
                        f"重複データが見つかりました（日付: {row.trade_date}, 金額: {row.payment_amount or row.deposit_amount}）。"
                        "このファイルの取り込みを中止します。"
                    )

            # すべての行が新規の場合のみ一括作成
            records = [
                MufgDepositCsvRaw(
                    bank=self.bank,
                    trade_date=row.trade_date,
                    summary=row.summary,
                    summary_detail=row.summary_detail,
                    payment_amount=row.payment_amount,
                    deposit_amount=row.deposit_amount,
                    balance=row.balance,
                    inout_type=row.inout_type,
                    memo=row.memo,
                    uncollected_flag=row.uncollected_flag,
                )
                for row in rows
            ]
            MufgDepositCsvRaw.objects.bulk_create(records)

        return len(rows)
