from django.contrib.auth.models import User
from django.db import models


class WardType(models.Model):
    name = models.CharField(verbose_name="病棟種", max_length=100, unique=True)

    def __str__(self):
        return self.name


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

    def __str__(self):
        return self.name


class City(models.Model):
    name = models.CharField(verbose_name="エリア", max_length=100, unique=True)

    def __str__(self):
        return self.name


class CitySector(models.Model):
    name = models.CharField(verbose_name="市区", max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.name


class Election(models.Model):
    name = models.CharField(verbose_name="選挙名", max_length=255, unique=True)
    execution_date = models.DateField(verbose_name="執行日")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.name


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


class ElectionLedger(models.Model):
    """
    選挙事務用の請求者名簿と事務処理簿の入力項目をまとめた、事務処理台帳

    Note: モデルフィールドで choices 属性が設定されている場合、get_FOO_display() メソッドが自動生成される。
            これにより、レコード内部値に代替する表示名（"代理・直接" など）を取得することができます。
    >>> ledger = ElectionLedger.objects.get(id=1)
    >>> print(ledger.get_billing_method_display())

    Attributes:
        - election (ForeignKey): 選挙名
        - voter (ForeignKey): 投票者氏名
        - vote_ward (ForeignKey): 病棟名
        - vote_city_sector (ForeignKey): 投票区名
        - remark (CharField): 備考
        - billing_method (CharField): 投票用紙の請求方法
        - proxy_billing_request_date (DateField): 代理請求依頼日
        - proxy_billing_date (DateField): 代理請求日
        - ballot_received_date (DateField): 投票用紙受領日
        - vote_date (DateField): 投票日（投票済みか否かを判断できる）
        - vote_place (ForeignKey): 投票場所
        - voter_witness (ForeignKey): 投票立会人
        - applied_for_proxy_voting (BooleanField): 代理投票申請の有無
        - delivery_date (DateField): 投票用紙送付日
        - created_at (DateTimeField): 取込日時
        - updated_at (DateTimeField): 更新日時
    """

    election = models.ForeignKey(
        Election, verbose_name="選挙名", on_delete=models.CASCADE
    )
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
    remark = models.CharField(
        verbose_name="備考", max_length=255, null=True, blank=True
    )
    billing_method = models.IntegerField(
        verbose_name="投票用紙請求の方法",
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
    vote_observer = models.ForeignKey(
        User,
        verbose_name="投票立会人",
        on_delete=models.CASCADE,
        related_name="voter_witness",
        null=True,
        blank=True,
    )
    applied_for_proxy_voting = models.BooleanField(
        verbose_name="代理投票申請の有無",
        default=False,
    )
    delivery_date = models.DateField(
        verbose_name="投票用紙送付日", null=True, blank=True
    )
    created_at = models.DateTimeField(verbose_name="取込日", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"{self.election.name}, {self.voter}（病棟: {self.vote_ward.name}）"
