from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.urls import path

from .domain.service.reading_support_draft import (
    ReadingSupportDraftGenerationError,
    ReadingSupportDraftService,
)
from .domain.service.reading_support_import import ReadingSupportCsvImporter
from .forms import ReadingSupportCsvImportForm, ReadingSupportDraftGenerationForm
from .models import (
    ReadingSupportDraft,
    ReadingSupportDraftCandidate,
    ReadingSupportEntry,
)


@admin.register(ReadingSupportEntry)
class ReadingSupportEntryAdmin(admin.ModelAdmin):
    """読み仮名支援辞書の登録・編集画面。"""

    change_list_template = "admin/kokkai/readingsupportentry/change_list.html"
    list_display = (
        "surface",
        "reading",
        "get_entry_type_display",
        "category",
        "is_active",
        "updated_at",
    )
    list_filter = ("entry_type", "is_active", "category")
    search_fields = ("surface", "reading", "description", "category")
    readonly_fields = ("normalized_surface", "created_at", "updated_at")
    fieldsets = (
        (
            "辞書エントリ",
            {
                "fields": (
                    "entry_type",
                    "surface",
                    "normalized_surface",
                    "reading",
                    "is_active",
                )
            },
        ),
        (
            "用語情報（読み補正では任意）",
            {"fields": ("description", "category", "source_url")},
        ),
        ("管理情報", {"fields": ("created_at", "updated_at")}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "csv-import/",
                self.admin_site.admin_view(self.csv_import_view),
                name="kokkai_readingsupportentry_csv_import",
            )
        ]
        return custom_urls + urls

    def csv_import_view(self, request):
        if request.method == "POST":
            form = ReadingSupportCsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                result = ReadingSupportCsvImporter().import_csv(
                    form.cleaned_data["file"].read(),
                    update_existing=form.cleaned_data["update_existing"],
                )
                if result.is_success:
                    self.message_user(
                        request,
                        (
                            f"CSVを取り込みました（新規 {result.created}件、"
                            f"更新 {result.updated}件、スキップ {result.skipped}件）。"
                        ),
                        messages.SUCCESS,
                    )
                else:
                    for error in result.errors:
                        self.message_user(
                            request,
                            f"{error.line_number}行目: {error.message}",
                            messages.ERROR,
                        )
                context = {
                    **self.admin_site.each_context(request),
                    "opts": self.model._meta,
                    "form": form,
                    "result": result,
                }
                return TemplateResponse(
                    request,
                    "admin/kokkai/readingsupportentry/csv_import.html",
                    context,
                )
        else:
            form = ReadingSupportCsvImportForm()
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
        }
        return TemplateResponse(
            request,
            "admin/kokkai/readingsupportentry/csv_import.html",
            context,
        )


class ReadingSupportDraftCandidateInline(admin.TabularInline):
    """GPT下書き内の候補を編集・承認するインライン。"""

    model = ReadingSupportDraftCandidate
    extra = 0
    fields = (
        "entry_type",
        "surface",
        "reading",
        "description",
        "category",
        "source_url",
        "needs_review",
        "is_approved",
        "is_registered",
        "review_note",
        "registered_entry",
    )
    readonly_fields = ("is_registered", "registered_entry")


@admin.register(ReadingSupportDraft)
class ReadingSupportDraftAdmin(admin.ModelAdmin):
    """Web／GPT取り込みの候補下書きと承認を管理する画面。"""

    change_list_template = "admin/kokkai/readingsupportdraft/change_list.html"
    list_display = ("id", "source_url", "status", "model_name", "created_at")
    list_filter = ("status",)
    search_fields = ("source_url", "source_text", "error_message")
    readonly_fields = ("model_name", "created_by", "created_at", "updated_at")
    inlines = (ReadingSupportDraftCandidateInline,)
    actions = ("register_approved_candidates", "reject_drafts")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "generate/",
                self.admin_site.admin_view(self.generate_view),
                name="kokkai_readingsupportdraft_generate",
            )
        ]
        return custom_urls + urls

    @admin.action(description="承認済み候補を辞書へ登録する")
    def register_approved_candidates(self, request, queryset):
        for draft in queryset:
            result = ReadingSupportDraftService().register_approved_candidates(draft)
            if result.errors:
                for error in result.errors:
                    self.message_user(
                        request, f"下書き #{draft.pk}: {error}", messages.ERROR
                    )
            else:
                self.message_user(
                    request,
                    f"下書き #{draft.pk}から{result.registered}件を辞書へ登録しました。",
                    messages.SUCCESS,
                )

    @admin.action(description="選択した下書きを却下する")
    def reject_drafts(self, request, queryset):
        updated = queryset.update(status=ReadingSupportDraft.Status.REJECTED)
        self.message_user(
            request, f"{updated}件の下書きを却下しました。", messages.SUCCESS
        )

    def generate_view(self, request):
        if request.method == "POST":
            form = ReadingSupportDraftGenerationForm(request.POST)
            if form.is_valid():
                try:
                    draft = ReadingSupportDraftService().create_draft(
                        source_url=form.cleaned_data["source_url"],
                        source_text=form.cleaned_data["source_text"],
                        created_by=request.user,
                    )
                except ReadingSupportDraftGenerationError as error:
                    form.add_error(None, str(error))
                else:
                    self.message_user(
                        request,
                        f"候補下書き #{draft.pk}を作成しました。内容を確認してから承認してください。",
                        messages.SUCCESS,
                    )
                    return self.response_post_save_add(request, draft)
        else:
            form = ReadingSupportDraftGenerationForm()
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
        }
        return TemplateResponse(
            request,
            "admin/kokkai/readingsupportdraft/generate.html",
            context,
        )
