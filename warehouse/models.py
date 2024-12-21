from django.contrib.auth.models import User
from django.db import models


class Warehouse(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.TextField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    width = models.PositiveSmallIntegerField()
    height = models.PositiveSmallIntegerField()
    depth = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return self.name


class Company(models.Model):
    name = models.TextField(blank=True, null=True)
    address = models.TextField(blank=False, null=False)

    def __str__(self):
        return self.name


class BillingPerson(models.Model):
    """請求担当者"""

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.TextField(blank=True, null=True)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return self.name


class RentalStatus(models.Model):
    """貸し出し等のステータス"""

    STOCK: int = 1
    RENTAL: int = 2
    name = models.TextField()


class BillingStatus(models.Model):
    """請求中、請求完了、請求無効"""

    BILLING: int = 1
    DONE: int = 2
    INVALID: int = 3

    name = models.TextField()

    def __str__(self):
        return self.name


class Staff(models.Model):
    name = models.CharField("表示名", max_length=50)
    description = models.TextField(verbose_name="自己紹介", null=True, blank=True)
    image = models.ImageField(
        upload_to="warehouse/staff",
        verbose_name="プロフィール画像",
        null=True,
        blank=True,
    )
    warehouses = models.ManyToManyField(Warehouse, through="WarehouseStaff")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return self.name


class WarehouseStaff(models.Model):
    """中間テーブル: 倉庫とスタッフの関連を管理"""

    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["warehouse", "staff"]]


class Invoice(models.Model):
    """インボイス（請求書）機材の名称、数量、備品番号,S/N"""

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    billing_person = models.ForeignKey(BillingPerson, on_delete=models.CASCADE)
    rental_start_date = models.DateField(null=True, blank=True)
    rental_end_date = models.DateField(null=True, blank=True)
    billing_status = models.ForeignKey(
        BillingStatus, default=1, on_delete=models.CASCADE
    )
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Item(models.Model):
    """アイテム。代替は片方を修理に変えて、invoiceに紐づけてもう片方を貸出中にする"""

    serial_number = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50, blank=False, null=False)
    price = models.PositiveSmallIntegerField()
    pos_x = models.PositiveIntegerField()
    pos_y = models.PositiveSmallIntegerField()
    pos_z = models.PositiveIntegerField()
    rental_status = models.ForeignKey(RentalStatus, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return self.name
