from django.contrib import admin

from taxonomy.models import LivestockDistributionDataset


@admin.register(LivestockDistributionDataset)
class LivestockDistributionDatasetAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "survey_year",
        "source_stat_code",
        "retrieved_at",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "survey_year", "source_stat_code")
    search_fields = ("title", "source_name", "source_stat_code")
