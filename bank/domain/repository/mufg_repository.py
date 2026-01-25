from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from bank.models import Bank, MufgDepositCsvRaw
from bank.domain.valueobject.mufg_csv_row import MufgCsvRow


class MufgRepository:
    def __init__(self, bank: Bank):
        self.bank = bank

    def get_living_cost_transactions(self, only_40k: bool = False):
        """
        生活費取引を抽出する。
        - 摘要に「カード」「ｶｰﾄﾞ」「カ－ド」「カ‐ド」のいずれかを含む
        - 支払い金額（payment_amount）が数値として存在する
        - 2018年4月以降の取引については、差引残高（balance） == 0 であること
          (2018年3月以前はメイン口座として利用していたため、残高0条件は不要)
        """
        # 基底条件：摘要にカードを含み、支払い金額がある
        # 「カ－ド」(全角ダッシュ)や「カ‐ド」(ハイフン)なども対象に含める
        card_keywords = ["カード", "ｶｰﾄﾞ", "カ－ド", "カ‐ド"]
        summary_filter = Q()
        for kw in card_keywords:
            summary_filter |= Q(summary__contains=kw)

        base_filter = summary_filter
        base_filter &= Q(bank=self.bank)
        base_filter &= Q(payment_amount__isnull=False)

        # 期間による条件分岐
        # 1. 2018年3月以前: 残高条件なし
        condition1 = Q(trade_date__lte="2018-03-31")

        # 2. 2018年4月以降: 残高0または摘要が「ｶｰﾄﾞ」(半角)で残高0
        # (Eco通帳の仕様変更により、支払即時引落の場合は残高0になる運用ルール)
        condition2 = Q(trade_date__gte="2018-04-01") & Q(balance=0)

        query = MufgDepositCsvRaw.objects.filter(
            base_filter & (condition1 | condition2)
        )

        if only_40k:
            query = query.filter(payment_amount=40000)

        return query.order_by("trade_date")

    def save_rows(self, rows: list[MufgCsvRow]) -> dict:
        """
        行を保存する。1件でも重複があれば、そのファイル全体の保存を中止する。
        :param rows: 保存する行リスト
        :return: 月ごとの新規作成件数
        :raises ValueError: 重複データが見つかった場合
        """
        monthly_counts = {}
        seen_in_batch = set()

        with transaction.atomic():
            for row in rows:
                # DBの制約(UniqueConstraint)に合わせたキーを作成
                # bank, trade_date, summary, summary_detail, payment_amount, deposit_amount, balance, inout_type
                row_key = (
                    row.trade_date,
                    row.summary,
                    row.summary_detail,
                    row.payment_amount,
                    row.deposit_amount,
                    row.balance,
                    row.inout_type,
                )

                # 同一バッチ内での重複チェック
                if row_key in seen_in_batch:
                    # エラーメッセージに「重複」という文字を含めることで呼び出し側で判定している
                    raise ValueError(
                        f"ファイル内で重複データが見つかりました（日付: {row.trade_date}, 摘要: {row.summary}, 摘要内容: {row.summary_detail}, 金額: {row.payment_amount or row.deposit_amount}, 残高: {row.balance}）。"
                        "同一の取引が複数行含まれている可能性があります。"
                    )
                seen_in_batch.add(row_key)

                # DB既存データとの重複チェック
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
                    # エラーメッセージに「重複」という文字を含めることで呼び出し側で判定している
                    raise ValueError(
                        f"既に登録済みの重複データが見つかりました（日付: {row.trade_date}, 金額: {row.payment_amount or row.deposit_amount}）。"
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
