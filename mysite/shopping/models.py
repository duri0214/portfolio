"""models.py"""
from django.conf import settings
from django.db import models
from django.utils import timezone


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
