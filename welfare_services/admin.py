from django.contrib import admin

from .models import Facility, FacilityAvailability, FacilityReview


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "postal_code", "address", "phone", "updated_at")
    search_fields = ("name", "address", "postal_code")
    list_filter = ("coordinate_system", "updated_at")
    date_hierarchy = "updated_at"
    fieldsets = (
        (
            "基本情報",
            {
                "fields": (
                    "name",
                    "postal_code",
                    "address",
                    "phone",
                    "fax",
                )
            },
        ),
        ("位置情報", {"fields": ("latitude", "longitude", "coordinate_system")}),
    )


@admin.register(FacilityAvailability)
class FacilityAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("facility", "status", "available_count", "updated_at")
    list_filter = ("status", "updated_at")
    search_fields = ("facility__name", "remarks")
    date_hierarchy = "updated_at"
    raw_id_fields = ("facility",)


@admin.register(FacilityReview)
class FacilityReviewAdmin(admin.ModelAdmin):
    list_display = (
        "facility",
        "affiliated_facility_name",
        "reviewer_name",
        "certificate_type",
        "certificate_number",
        "rating",
        "created_at",
        "is_approved",
    )
    list_filter = ("rating", "is_approved", "created_at", "certificate_type")
    search_fields = ("facility__name", "reviewer_name", "comment", "certificate_number")
    date_hierarchy = "created_at"
    raw_id_fields = ("facility",)
    actions = ["approve_reviews", "unapprove_reviews"]

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()}件のレビューを承認しました。")

    approve_reviews.short_description = "選択したレビューを承認する"

    def unapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(
            request, f"{queryset.count()}件のレビューの承認を取り消しました。"
        )

    unapprove_reviews.short_description = "選択したレビューの承認を取り消す"
