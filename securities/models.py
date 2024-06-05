from django.db import models


class Company(models.Model):
    edinet_code = models.CharField("ＥＤＩＮＥＴコード", max_length=6, null=True)
    type_of_submitter = models.CharField("提出者種別", max_length=30, null=True)
    listing_status = models.CharField("上場区分", max_length=3, null=True)
    consolidated_status = models.CharField("連結の有無", max_length=1, null=True)
    capital = models.IntegerField("資本金", null=True)
    end_fiscal_year = models.CharField("決算日", max_length=6, null=True)
    submitter_name = models.CharField("提出者名", max_length=100, null=True)
    submitter_name_en = models.CharField("提出者名（英字）", max_length=100, null=True)
    submitter_name_kana = models.CharField(
        "提出者名（ヨミ）", max_length=100, null=True
    )
    address = models.CharField("所在地", max_length=255, null=True)
    submitter_industry = models.CharField("提出者業種", max_length=25, null=True)
    securities_code = models.CharField("証券コード", max_length=5, null=True)
    corporate_number = models.CharField("提出者法人番号", max_length=13, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Counting(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True)
    period_start = models.DateField("期間（自）", null=True)
    period_end = models.DateField("期間（至）", null=True)
    submit_date = models.DateField("提出日時")
    avg_salary = models.IntegerField("平均年間給与（円）", null=True)
    avg_tenure = models.FloatField("平均勤続年数（年）", null=True)
    avg_age = models.FloatField("平均年齢（歳）", null=True)
    number_of_employees = models.IntegerField("従業員数（人）", null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["company", "submit_date"]
