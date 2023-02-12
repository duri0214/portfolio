from django.conf import settings
from django.db import models
from django.utils import timezone


class Store(models.Model):
    """店舗"""
    name = models.CharField('店名', max_length=255)

    def __str__(self):
        return self.name


class Staff(models.Model):
    """店舗スタッフ"""
    name = models.CharField('表示名', max_length=50)
    description = models.TextField(verbose_name='自己紹介', null=True, blank=True)
    image = models.ImageField(upload_to='shopping/staff', verbose_name='プロフィール画像', null=True, blank=True)
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='ログインユーザー', on_delete=models.CASCADE
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'store'],
                name='unique_user_store'
            ),
        ]

    def __str__(self):
        return f'{self.store.name} - {self.name}'


class Products(models.Model):
    """商品"""
    code = models.CharField('商品コード', max_length=200)
    name = models.CharField('商品名', max_length=200)
    price = models.IntegerField('金額', default=0)
    description = models.TextField('説明')
    picture = models.ImageField('商品写真', upload_to='shopping/')
    created_at = models.DateTimeField(default=timezone.now)


class BuyingHistory(models.Model):
    """購入履歴"""
    product = models.ForeignKey(Products, verbose_name='商品名', on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='購入者', on_delete=models.PROTECT)
    was_sent = models.BooleanField('発送フラグ', default=False)
    stripe_id = models.CharField('タイトル', max_length=200)
    created_at = models.DateTimeField('日付', default=timezone.now)
