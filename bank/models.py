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
        db_table = "bank"
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


class MufgDepositCsvRaw(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT)

    trade_date = models.DateField(verbose_name="日付")
    summary = models.CharField(max_length=255, verbose_name="摘要")
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
        db_table = "mufg_deposit_csv_raw"
        verbose_name = "MUFG普通預金CSV Raw"
        verbose_name_plural = "MUFG普通預金CSV Raw"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "bank",
                    "trade_date",
                    "summary",
                    "summary_detail",
                    "balance",
                    "inout_type",
                ],
                name="unique_mufg_deposit_csv_raw",
            )
        ]
