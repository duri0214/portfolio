from django.contrib import admin

from .models import RokunoheLandRegistry


@admin.register(RokunoheLandRegistry)
class RokunoheLandRegistryAdmin(admin.ModelAdmin):
    list_display = (
        "ledger_type",
        "address",
        "coordinate",
        "registered_land_category",
        "current_land_category",
        "registered_area",
        "current_area",
    )
    search_fields = ("address", "coordinate")
