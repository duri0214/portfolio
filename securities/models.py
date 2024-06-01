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
