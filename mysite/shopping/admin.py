from django.contrib import admin
from .models import Staff, Store, Products, BuyingHistory

# Register your models here.
admin.site.register(Staff)
admin.site.register(Store)
admin.site.register(Products)
admin.site.register(BuyingHistory)
