from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from bank.models import Bank, MufgDepositCsvRaw, DepositSummaryMaster
from bank.domain.valueobject.mufg_csv_row import MufgCsvRow


class MufgRepository:
    def __init__(self, bank: Bank):
        self.bank = bank

    def get_living_cost_transactions(self, only_40k: bool = False):
        """
        生活費取引を抽出する。
        - 摘要マスタをJOINし、カテゴリ名が「カード」であるものを抽出する
        - 支払い金額（payment_amount）が数値として存在する
        - 2018年4月以降の取引については、差引残高（balance） == 0 であること
          (2018年3月以前はメイン口座として利用していたため、残高0条件は不要)
        """
        # 基底条件：カテゴリが「カード」であり、支払い金額がある
        # 摘要文字列を介して DepositSummaryMaster を外部結合
        # (Djangoのモデルにリレーションがないため、ExtraクエリやRawクエリ、あるいはリレーション定義が必要)
        # 既存の MufgDepositCsvRaw に summary_master property はあるが、クエリでJOINするには
        # マスタ側から引くか、リレーションを追加するのが望ましい。

        # 現状のモデル定義ではリレーションがないが、
        # 改修方針に「Repository / Query レイヤでマスタ JOIN を行う」とある。
        # Django ORM でリレーションがないフィールド同士を JOIN するには Filter 句でサブクエリを使うか、
        # モデルにリレーションを追加する必要がある。

        # models.py を見ると、MufgDepositCsvRaw.summary と DepositSummaryMaster.summary が対応している。
        # JOIN を実現するために、DepositSummaryMaster から summary リストを取得して IN で絞り込む方法もあるが、
        # JOIN と明記されているため、クエリレベルでの結合を目指す。

        # カテゴリ名が「カード」の摘要リストを取得
        summary_master_qs = DepositSummaryMaster.objects.filter(
            category__name="カード"
        ).values_list("summary", flat=True)

        base_filter = Q(bank=self.bank)
        base_filter &= Q(summary__in=summary_master_qs)
        base_filter &= Q(payment_amount__isnull=False)

        # 期間による条件分岐
        # 1. 2018年3月以前: 残高条件なし
        condition1 = Q(trade_date__lte="2018-03-31")

        # 2. 2018年4月以降: 残高0
        condition2 = Q(trade_date__gte="2018-04-01") & Q(balance=0)

        query = MufgDepositCsvRaw.objects.filter(
            base_filter & (condition1 | condition2)
        )

        if only_40k:
            query = query.filter(payment_amount=40000)

        return query.order_by("trade_date")

    def get_all_transactions(self):
        """
        全取引を取得する。
        """
        return MufgDepositCsvRaw.objects.filter(bank=self.bank).order_by("trade_date")

    def get_category_monthly_stats(self):
        """
        カテゴリ別・月別の統計情報を取得する。
        """
        from django.db.models import Sum
        from django.db.models.functions import TruncMonth

        # MufgDepositCsvRaw と DepositSummaryMaster を JOIN してカテゴリ情報を取得する
        # Django ORM でリレーションがないため、一旦全件取得して Python 側でマッピングするか、
        # あるいはサブクエリ等を利用する。ここでは効率のため、マスタを先に取得してマッピングする。

        masters = DepositSummaryMaster.objects.select_related("category").all()
        summary_to_category = {m.summary: m.category.name for m in masters}

        # 取引データを月ごとに集計（一旦メモリに乗せるが、MUFGデータは数千件程度なので許容範囲）
        transactions = (
            MufgDepositCsvRaw.objects.filter(bank=self.bank)
            .annotate(month=TruncMonth("trade_date"))
            .values("month", "summary", "payment_amount", "deposit_amount")
            .order_by("month")
        )

        stats = {}  # {(month, category): {'payment': sum, 'deposit': sum}}
        all_months = set()
        all_categories = set(summary_to_category.values())
        all_categories.add("未分類")

        for tx in transactions:
            month = tx["month"].strftime("%Y-%m")
            all_months.add(month)
            category = summary_to_category.get(tx["summary"], "未分類")

            key = (month, category)
            if key not in stats:
                stats[key] = {"payment": 0, "deposit": 0}

            stats[key]["payment"] += tx["payment_amount"] or 0
            stats[key]["deposit"] += tx["deposit_amount"] or 0

        return {
            "stats": stats,
            "months": sorted(list(all_months)),
            "categories": sorted(list(all_categories)),
        }

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
