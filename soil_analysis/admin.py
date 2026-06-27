from django.contrib import admin

from .models import (
    AgriculturalRegion,
    AgriculturalRiskReport,
    AgriculturalStatisticSnapshot,
    EstatDataset,
    RokunoheLandRegistry,
    SupplementalRiskIndicator,
)


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


@admin.register(AgriculturalRegion)
class AgriculturalRegionAdmin(admin.ModelAdmin):
    list_display = ("area_code", "prefecture_name", "name", "updated_at")
    search_fields = ("area_code", "prefecture_name", "name")


@admin.register(EstatDataset)
class EstatDatasetAdmin(admin.ModelAdmin):
    list_display = (
        "indicator_key",
        "display_name",
        "stats_data_id",
        "unit",
        "category",
    )
    search_fields = ("indicator_key", "display_name", "stats_data_id")


@admin.register(AgriculturalStatisticSnapshot)
class AgriculturalStatisticSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "region",
        "dataset",
        "period_label",
        "value",
        "fetched_at",
        "source_hash",
    )
    list_filter = ("region", "dataset")
    search_fields = ("region__area_code", "dataset__indicator_key", "period_label")


@admin.register(AgriculturalRiskReport)
class AgriculturalRiskReportAdmin(admin.ModelAdmin):
    list_display = (
        "region",
        "report_date",
        "unmanageable_candidate_area",
        "farmland_maintenance_rate",
    )
    list_filter = ("region", "report_date")


@admin.register(SupplementalRiskIndicator)
class SupplementalRiskIndicatorAdmin(admin.ModelAdmin):
    list_display = (
        "indicator_key",
        "display_name",
        "region_label",
        "period_label",
        "value",
        "unit",
        "category",
    )
    list_filter = ("region_label", "category")
    search_fields = ("indicator_key", "display_name", "source_name")
