"""models.py"""
from django.db import models

# Create your models here.
class StoreInformation(models.Model):
    """
    StoreInformation
    """
    category = models.IntegerField()
    searchword = models.CharField(null=True, blank=True, max_length=100)
    place_id = models.CharField(null=True, blank=True, max_length=200)
    shop_name = models.CharField(max_length=200)
    shop_latlng = models.CharField(max_length=100)
    create_at = models.DateTimeField(auto_now=True)

class SignageMenuName(models.Model):
    """
    SignageName
    """
    menu_code = models.CharField(primary_key=True, max_length=2)
    menu_name = models.CharField(max_length=100)
