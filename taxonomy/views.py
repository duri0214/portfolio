import json
import os

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.node import NodeTree
from taxonomy.domain.repository.breed import BreedRepository
from taxonomy.domain.repository.chicken_observations import (
    ChickenObservationsRepository,
)
from taxonomy.domain.repository.livestock_distribution import (
    LivestockDistributionDatasetRepository,
)
from taxonomy.domain.service.livestock_distribution_fetch import (
    CURRENT_DATE,
    LivestockDistributionApiError,
    LivestockDistributionFetchError,
    LivestockDistributionFetchService,
    LivestockDistributionParseError,
    LivestockDistributionSaveError,
    SOURCE_STAT_CODE,
    SOURCE_URL,
)
from taxonomy.domain.service.llm_taxonomy_candidate_review import (
    LLMTaxonomyCandidateReviewError,
    LLMTaxonomyCandidateReviewService,
)
from taxonomy.domain.valueobject.taxonomy_graph import TaxonomyGraph
from taxonomy.forms import (
    BreedForm,
    LLMTaxonomyCandidateForm,
    TaxonomyBreedCreateForm,
)
from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    LLMTaxonomyCandidate,
    Phylum,
    Species,
)


class IndexView(TemplateView):
    template_name = "taxonomy/index.html"

    def get_context_data(self, **kwargs):
        """
        コンテキストデータを設定。
        主にBreedRepositoryを使用して分類データを取得し、
        Breed分類ツリーとしてテンプレートに提供する。
        """
        context = super().get_context_data(**kwargs)

        # Breed分類ツリーの取得
        breed_entities = [
            BreedEntity(record) for record in BreedRepository.get_breed_hierarchy()
        ]
        tree = NodeTree(breed_entities)
        context["data"] = json.dumps(tree.export(), ensure_ascii=False)
        breed_detail_urls = {
            entity.breed_id: reverse("txo:breed_detail", kwargs={"pk": entity.breed_id})
            for entity in breed_entities
            if entity.breed_id is not None
        }
        graph = TaxonomyGraph.from_breed_entities(breed_entities, breed_detail_urls)
        context["graph_data"] = json.dumps(graph.to_payload(), ensure_ascii=False)

        return context


class ObservationView(TemplateView):
    template_name = "taxonomy/observation.html"

    def post(self, request, *args, **kwargs):
        """
        鶏の観察ページからe-Stat畜産統計を取得して登録します。
        """
        if not request.user.is_superuser:
            messages.error(request, "畜産統計データを取得する権限がありません。")
            return redirect("txo:observation")

        app_id = os.getenv("ESTAT_APP_ID")
        if not app_id:
            messages.error(
                request, "ESTAT_APP_ID が未設定のため、e-Stat APIを呼び出せません。"
            )
            return redirect("txo:observation")

        survey_year = self._get_posted_livestock_survey_year()
        if survey_year is None:
            messages.error(request, "取得年度は西暦の数値で指定してください。")
            return redirect("txo:observation")

        try:
            result = LivestockDistributionFetchService.fetch_and_save(
                app_id, survey_year
            )
        except LivestockDistributionApiError as error:
            messages.error(request, f"API取得失敗: {error}")
        except LivestockDistributionParseError as error:
            messages.error(request, f"パース失敗: {error}")
        except LivestockDistributionSaveError as error:
            messages.error(request, f"DB登録失敗: {error}")
        except LivestockDistributionFetchError as error:
            messages.error(request, str(error))
        else:
            retrieved_at = result.dataset.retrieved_at.isoformat()
            action = "取得しました" if result.created else "更新しました"
            messages.success(
                request,
                (
                    f"畜産統計データを{action}。"
                    f"対象年: {result.dataset.survey_year}年 / "
                    f"登録件数: {result.row_count}件 / 取得日: {retrieved_at}"
                ),
            )
        return redirect("txo:observation")

    def get_context_data(self, **kwargs):
        """
        Observationページのコンテキストデータを設定
        """
        context = super().get_context_data(**kwargs)

        # 餌の投入量と卵生産量データを取得
        feed_vs_egg = ChickenObservationsRepository.get_feed_vs_egg_production()
        context["feed_vs_egg"] = mark_safe(json.dumps(feed_vs_egg, ensure_ascii=False))

        # Feed Group別の産卵率データを取得
        context["feed_group_laying_rate"] = (
            ChickenObservationsRepository.get_feed_group_laying_rates_table()
        )
        survey_years = LivestockDistributionDatasetRepository.get_active_survey_years()
        selected_survey_year = self._get_selected_livestock_survey_year(survey_years)
        if selected_survey_year is None:
            livestock_dashboard = (
                LivestockDistributionDatasetRepository.get_latest_dashboard()
            )
        else:
            livestock_dashboard = (
                LivestockDistributionDatasetRepository.get_dashboard_by_survey_year(
                    selected_survey_year
                )
            )
        default_fetch_year = CURRENT_DATE().year
        if survey_years:
            default_fetch_year = survey_years[0]
        if selected_survey_year is not None:
            default_fetch_year = selected_survey_year

        context["livestock_survey_years"] = survey_years
        context["selected_livestock_survey_year"] = selected_survey_year
        context["default_livestock_fetch_year"] = default_fetch_year
        context["livestock_dashboard"] = livestock_dashboard
        context["livestock_source_stat_code"] = SOURCE_STAT_CODE
        context["livestock_source_url"] = SOURCE_URL
        if livestock_dashboard is not None:
            context["livestock_distribution_json"] = livestock_dashboard.to_payload()
        else:
            context["livestock_distribution_json"] = {
                "categories": [],
                "maps": {},
            }

        return context

    def _get_selected_livestock_survey_year(
        self, survey_years: list[int]
    ) -> int | None:
        survey_year = self.request.GET.get("livestock_year")
        if not survey_year:
            return None
        try:
            selected_survey_year = int(survey_year)
        except ValueError:
            raise Http404("対象年は数値で指定してください。")
        if selected_survey_year not in survey_years:
            raise Http404("指定された対象年の畜産統計データはありません。")
        return selected_survey_year

    def _get_posted_livestock_survey_year(self) -> int | None:
        survey_year = self.request.POST.get("livestock_survey_year")
        if not survey_year:
            return None
        try:
            return int(survey_year)
        except ValueError:
            return None


class TaxonomyBreedCreateView(FormView):
    """
    分類階層と品種を1画面で登録するビュー。

    既存階層の選択と不足階層の追加を同じフォームで扱い、保存後は
    登録した品種の詳細ページへ遷移する。
    """

    form_class = TaxonomyBreedCreateForm
    template_name = "taxonomy/breed_form.html"

    def form_valid(self, form):
        self.breed = form.save()
        messages.success(self.request, f"{self.breed.name} を登録しました。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("txo:breed_detail", kwargs={"pk": self.breed.pk})

    def form_invalid(self, form):
        messages.error(
            self.request, "登録できませんでした。入力内容を確認してください。"
        )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hierarchy_json"] = json.dumps(
            self._build_hierarchy_options(), ensure_ascii=False
        )
        return context

    def _build_hierarchy_options(self):
        return {
            "phylum": [
                {"id": item.id, "name": item.name, "parent": item.kingdom_id}
                for item in Phylum.objects.order_by("kingdom_id", "name")
            ],
            "classification": [
                {"id": item.id, "name": item.name, "parent": item.phylum_id}
                for item in Classification.objects.order_by("phylum_id", "name")
            ],
            "family": [
                {"id": item.id, "name": item.name, "parent": item.classification_id}
                for item in Family.objects.order_by("classification_id", "name")
            ],
            "genus": [
                {"id": item.id, "name": item.name, "parent": item.family_id}
                for item in Genus.objects.order_by("family_id", "name")
            ],
            "species": [
                {"id": item.id, "name": item.name, "parent": item.genus_id}
                for item in Species.objects.order_by("genus_id", "name")
            ],
        }


class LLMTaxonomyCandidateListView(ListView):
    """
    LLM生成分類候補をレビュー状態ごとに一覧表示するビュー。
    """

    model = LLMTaxonomyCandidate
    template_name = "taxonomy/llm_candidate_list.html"
    context_object_name = "candidates"

    def get_queryset(self):
        return LLMTaxonomyCandidate.objects.select_related(
            "approved_breed",
            "reviewed_by",
        ).order_by("status", "-created_at")


class LLMTaxonomyCandidateCreateView(CreateView):
    """
    LLM生成分類候補を未確認データとして登録するビュー。
    """

    model = LLMTaxonomyCandidate
    form_class = LLMTaxonomyCandidateForm
    template_name = "taxonomy/llm_candidate_form.html"
    success_url = reverse_lazy("txo:llm_candidate_list")

    def form_valid(self, form):
        messages.success(self.request, "LLM生成候補をレビュー待ちとして保存しました。")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request, "保存できませんでした。入力内容を確認してください。"
        )
        return super().form_invalid(form)


class LLMTaxonomyCandidateApproveView(View):
    """
    LLM生成分類候補を承認し、確認済みtaxonomyデータへ登録するビュー。
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "LLM生成候補を承認する権限がありません。")
            return redirect("txo:llm_candidate_list")

        try:
            breed = LLMTaxonomyCandidateReviewService.approve(
                kwargs["pk"],
                request.user,
            )
        except LLMTaxonomyCandidateReviewError as error:
            messages.error(request, str(error))
            return redirect("txo:llm_candidate_list")

        messages.success(
            request,
            f"{breed.name} を確認済みtaxonomyデータとして登録しました。",
        )
        return redirect("txo:breed_detail", pk=breed.pk)


class LLMTaxonomyCandidateRejectView(View):
    """
    LLM生成分類候補を確認済みtaxonomyデータへ登録せず却下するビュー。
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "LLM生成候補を却下する権限がありません。")
            return redirect("txo:llm_candidate_list")

        try:
            LLMTaxonomyCandidateReviewService.reject(kwargs["pk"], request.user)
        except LLMTaxonomyCandidateReviewError as error:
            messages.error(request, str(error))
            return redirect("txo:llm_candidate_list")

        messages.success(request, "LLM生成候補を却下しました。")
        return redirect("txo:llm_candidate_list")


class BreedListView(ListView):
    """
    品種レコードを分類階層付きで一覧表示するビュー。
    """

    model = Breed
    template_name = "taxonomy/breed_list.html"
    context_object_name = "breeds"

    def get_queryset(self):
        return Breed.objects.select_related(
            "species__genus__family__classification__phylum__kingdom",
            "natural_monument",
        ).order_by(
            "species__genus__family__classification__phylum__kingdom__name",
            "species__genus__family__classification__phylum__name",
            "species__genus__family__classification__name",
            "species__genus__family__name",
            "species__genus__name",
            "species__name",
            "name",
        )


class BreedDetailView(DetailView):
    """
    1件の品種レコードと分類階層を表示するビュー。
    """

    model = Breed
    template_name = "taxonomy/breed_detail.html"
    context_object_name = "breed"
    queryset = Breed.objects.select_related(
        "species__genus__family__classification__phylum__kingdom",
        "natural_monument",
    )


class BreedUpdateView(UpdateView):
    """
    既存の品種レコードを編集するビュー。
    """

    model = Breed
    form_class = BreedForm
    template_name = "taxonomy/breed_edit.html"
    context_object_name = "breed"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"{self.object.name} を更新しました。")
        return response

    def get_success_url(self):
        return reverse_lazy("txo:breed_detail", kwargs={"pk": self.object.pk})


class BreedDeleteView(DeleteView):
    """
    品種レコードを確認画面経由で削除するビュー。
    """

    model = Breed
    template_name = "taxonomy/breed_confirm_delete.html"
    context_object_name = "breed"
    success_url = reverse_lazy("txo:breed_list")
    queryset = Breed.objects.select_related(
        "species__genus__family__classification__phylum__kingdom"
    )

    def form_valid(self, form):
        name = self.object.name
        response = super().form_valid(form)
        messages.success(self.request, f"{name} を削除しました。")
        return response


class KingdomCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class PhylumCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class ClassificationCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class FamilyCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class GenusCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class SpeciesCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class BreedCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class TagCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class BreedTagUpdateView(UpdateView):
    success_url = reverse_lazy("txo:index")
