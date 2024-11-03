from django.contrib.auth.models import User
from django.db import models


class WardType(models.Model):
    name = models.CharField(verbose_name="病棟種", max_length=100, unique=True)


class Ward(models.Model):
    abbreviation = models.CharField(verbose_name="略称", unique=True, max_length=10)
    ward_type = models.ForeignKey(
        WardType, verbose_name="病棟種", on_delete=models.CASCADE
    )
    name = models.CharField(
        verbose_name="病棟名", max_length=100, null=False, blank=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class City(models.Model):
    name = models.CharField(verbose_name="エリア", max_length=100, unique=True)


class CitySector(models.Model):
    name = models.CharField(verbose_name="市区", max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class Election(models.Model):
    name = models.CharField(verbose_name="選挙名", max_length=255, unique=True)
    execution_date = models.DateField(verbose_name="執行日")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class VotePlace(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class UserAttribute(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    address = models.TextField(verbose_name="住所")
    date_of_birth = models.DateField(verbose_name="生年月日")


BILLING_METHOD_CHOICES = [
    (1, "代理・直接"),
    (2, "代理・郵便"),
]
PROXY_VOTING_CHOICES = [(1, "無"), (2, "有")]


class ElectionLedger(models.Model):
    """
    選挙事務用の請求者名簿と事務処理簿の入力項目をガッチャンコした、事務処理台帳

    Note: モデルフィールドに choices を設定すると、自動的に _get_FOO_display() メソッドが生成され、登録された "代理・直接" などの名称を追うことができます
    >>> ledger = ElectionLedger.objects.get(id=1)
    >>> print(ledger.get_billing_method_display())

    Attributes:
        - election (ForeignKey): 選挙名を表す `Election` モデルへの外部キー
        - voter (ForeignKey): 投票者を表す `User` モデルへの外部キー
        - vote_ward (ForeignKey): 投票病棟を表す `Ward` モデルへの外部キー
        - vote_city_sector (ForeignKey): 投票都市区を表す `CitySector` モデルへの外部キー
        - remark (CharField): 備考
        - billing_method (CharField): 投票用紙請求の方法
        - proxy_billing_request_date (DateField): 代理請求の依頼を受けた日
        - proxy_billing_date (DateField): 代理請求日
        - ballot_received_date (DateField): 投票用紙受領日
        - vote_date (DateField): 投票日
        - vote_place (ForeignKey): 投票場所を表す `VotePlace` モデルへの外部キー
        - voter_witness (ForeignKey): 投票者証人を表す `User` モデルへの外部キー
        - whether_to_apply_for_proxy_voting (CharField): 代理投票申請の有無
        - delivery_date (DateField): 投票用紙送付日
        - created_at (DateTimeField): 取込日
        - updated_at (DateTimeField): The date and time when the ledger entry was last updated.
    """

    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    voter = models.ForeignKey(
        User,
        verbose_name="選挙人氏名",
        on_delete=models.CASCADE,
        related_name="voter",
    )
    vote_ward = models.ForeignKey(Ward, verbose_name="病棟", on_delete=models.CASCADE)
    vote_city_sector = models.ForeignKey(
        CitySector, verbose_name="投票区", on_delete=models.CASCADE
    )
    remark = models.CharField(max_length=255, null=True, blank=True)
    billing_method = models.CharField(
        verbose_name="投票用紙請求の方法",
        max_length=5,
        choices=BILLING_METHOD_CHOICES,
        null=True,
        blank=True,
    )
    proxy_billing_request_date = models.DateField(
        verbose_name="代理請求の依頼を受けた日", null=True, blank=True
    )
    proxy_billing_date = models.DateField(
        verbose_name="代理請求日", null=True, blank=True
    )
    ballot_received_date = models.DateField(
        verbose_name="投票用紙受領日", null=True, blank=True
    )
    vote_date = models.DateField(verbose_name="投票日", null=True, blank=True)
    vote_place = models.ForeignKey(
        VotePlace,
        verbose_name="投票場所",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    voter_witness = models.ForeignKey(
        User,
        verbose_name="投票立会人",
        on_delete=models.CASCADE,
        related_name="voter_witness",
        null=True,
        blank=True,
    )
    whether_to_apply_for_proxy_voting = models.CharField(
        verbose_name="代理投票申請の有無",
        max_length=1,
        choices=PROXY_VOTING_CHOICES,
        null=True,
        blank=True,
    )
    delivery_date = models.DateField(
        verbose_name="投票用紙送付日", null=True, blank=True
    )
    created_at = models.DateTimeField(verbose_name="取込日", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
