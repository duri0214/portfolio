from django.db import models


class Edinet(models.Model):
    class Meta:
        db_table = "securities_m_edinet"

    edinet_code = models.CharField("ＥＤＩＮＥＴコード", max_length=6)
    type_of_submitter = models.CharField("提出者種別", max_length=30)
    listing_status = models.CharField("上場区分", max_length=3)
    consolidated_status = models.CharField("連結の有無", max_length=1)
    capital = models.FloatField("資本金")
    end_fiscal_year = models.CharField("決算日", max_length=5)
    submitter_name = models.CharField("提出者名", max_length=100)
    submitter_name_en = models.CharField("提出者名（英字）", max_length=100)
    submitter_name_kana = models.CharField("提出者名（ヨミ）", max_length=100)
    address = models.CharField("所在地", max_length=255)
    submitter_industry = models.CharField("提出者業種", max_length=25)
    securities_code = models.CharField("証券コード", max_length=5)
    corporate_number = models.CharField("法人番号", max_length=13)
