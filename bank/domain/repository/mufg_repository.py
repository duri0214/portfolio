from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncMonth
from bank.models import Bank, MufgDepositCsvRaw
from bank.domain.valueobject.mufg_csv_row import MufgCsvRow


class MufgRepository:
    def __init__(self, bank: Bank):
        self.bank = bank

    def save_rows(self, rows: list[MufgCsvRow]) -> dict:
        """
        行を保存する。1件でも重複があれば、そのファイル全体の保存を中止する。
        :param rows: 保存する行リスト
        :return: 月ごとの新規作成件数
        :raises ValueError: 重複データが見つかった場合
        """
        monthly_counts = {}
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

                # 月ごとのカウント
                month_key = row.trade_date.strftime("%Y-%m")
                monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

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

        return monthly_counts

    def delete_all_data(self) -> dict:
        """
        この口座に関連するすべてのデータを削除する。
        :return: 月ごとの削除件数
        """
        # 削除前に月ごとの集計を取得
        stats = (
            MufgDepositCsvRaw.objects.filter(bank=self.bank)
            .annotate(month=TruncMonth("trade_date"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        monthly_counts = {
            item["month"].strftime("%Y-%m"): item["count"] for item in stats
        }

        with transaction.atomic():
            MufgDepositCsvRaw.objects.filter(bank=self.bank).delete()

        return monthly_counts
