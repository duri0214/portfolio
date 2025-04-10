from django.contrib import admin

from .models import Staff, Store, Product, BuyingHistory

# Register your models here.
admin.site.register(Staff)
admin.site.register(Store)
admin.site.register(Product)
admin.site.register(BuyingHistory)
