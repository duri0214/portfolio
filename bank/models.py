from django.db import models


class Bank(models.Model):
    name = models.CharField(max_length=100, verbose_name="銀行名")
    financial_code = models.CharField(max_length=10, verbose_name="金融機関コード")
    branch_code = models.CharField(
        max_length=3, null=True, blank=True, verbose_name="店番"
    )
    account_number = models.CharField(
        max_length=7, null=True, blank=True, verbose_name="口座番号"
    )
    remark = models.TextField(null=True, blank=True, verbose_name="備考")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "銀行マスタ"
        verbose_name_plural = "銀行マスタ"
        constraints = [
            models.UniqueConstraint(
                fields=["financial_code", "branch_code", "account_number"],
                name="unique_bank_account",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.branch_code}-{self.account_number})"


class DepositSummaryCategory(models.Model):
    """
    摘要カテゴリマスタ
    [通帳の明細ページの「摘要（お客様メモ）」欄の表示内容を教えてください。]
    (https://faq01.bk.mufg.jp/faq/show/278?site_domain=default)
    """

    name = models.CharField(max_length=100, verbose_name="カテゴリ名")
    description = models.TextField(null=True, blank=True, verbose_name="説明")
    display_order = models.IntegerField(default=0, verbose_name="表示順")

    class Meta:
        verbose_name = "摘要カテゴリマスタ"
        verbose_name_plural = "摘要カテゴリマスタ"

    def __str__(self):
        return self.name


class DepositSummaryMaster(models.Model):
    """
    摘要マスタ
    [通帳の明細ページの「摘要（お客様メモ）」欄の表示内容を教えてください。]
    (https://faq01.bk.mufg.jp/faq/show/278?site_domain=default)
    """

    summary = models.CharField(
        max_length=255, unique=True, verbose_name="摘要（CSV表記）"
    )
    category = models.ForeignKey(
        DepositSummaryCategory, on_delete=models.PROTECT, verbose_name="カテゴリ"
    )
    remark = models.TextField(null=True, blank=True, verbose_name="説明文（公式）")

    class Meta:
        verbose_name = "摘要マスタ"
        verbose_name_plural = "摘要マスタ"

    def __str__(self):
        return self.summary


class MufgDepositCsvRaw(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT)

    trade_date = models.DateField(verbose_name="日付")
    summary = models.CharField(max_length=255, verbose_name="摘要")

    @property
    def summary_master(self):
        """
        摘要文字列に完全一致する摘要マスタを返す。
        """
        return DepositSummaryMaster.objects.filter(summary=self.summary).first()

    summary_detail = models.CharField(max_length=255, verbose_name="摘要内容")

    payment_amount = models.IntegerField(
        null=True, blank=True, verbose_name="支払い金額"
    )
    deposit_amount = models.IntegerField(
        null=True, blank=True, verbose_name="預かり金額"
    )
    balance = models.IntegerField(verbose_name="差引残高")

    memo = models.CharField(max_length=255, null=True, blank=True, verbose_name="メモ")
    uncollected_flag = models.CharField(
        max_length=10, null=True, blank=True, verbose_name="未資金化区分"
    )
    inout_type = models.CharField(
        max_length=10, null=True, blank=True, verbose_name="入払区分"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "MUFG普通預金CSV Raw"
        verbose_name_plural = "MUFG普通預金CSV Raw"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "bank",
                    "trade_date",
                    "summary",
                    "summary_detail",
                    "payment_amount",
                    "deposit_amount",
                    "balance",
                    "inout_type",
                ],
                name="unique_mufg_deposit_csv_raw",
            )
        ]
