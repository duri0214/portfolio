from django.contrib import admin

from .models import Store, Product, BuyingHistory, UserAttribute


@admin.register(UserAttribute)
class UserAttributeAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "nickname", "store", "created_at")
    list_filter = ("role", "store")
    search_fields = ("user__username", "nickname")


admin.site.register(Store)
admin.site.register(Product)
admin.site.register(BuyingHistory)
