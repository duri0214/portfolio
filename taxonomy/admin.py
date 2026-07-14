from django.contrib import admin

from taxonomy.models import LLMTaxonomyCandidate, LivestockDistributionDataset


@admin.register(LLMTaxonomyCandidate)
class LLMTaxonomyCandidateAdmin(admin.ModelAdmin):
    list_display = (
        "breed_name",
        "species_name",
        "status",
        "source_name",
        "external_taxon_id",
        "reviewed_at",
        "created_at",
    )
    list_filter = ("status", "created_at", "reviewed_at")
    search_fields = (
        "breed_name",
        "species_name",
        "genus_name",
        "source_name",
        "external_taxon_id",
    )
    readonly_fields = ("approved_breed", "reviewed_by", "reviewed_at")


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
