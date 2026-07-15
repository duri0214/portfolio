import json
import logging
import os
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Case, IntegerField, Value, When
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
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
from taxonomy.domain.service.llm_taxonomy_candidate_generation import (
    LLMTaxonomyCandidateGenerationError,
    LLMTaxonomyCandidateGenerationService,
)
from taxonomy.domain.repository.llm_taxonomy_candidate import (
    LLMTaxonomyCandidateRepository,
)
from taxonomy.domain.valueobject.taxonomy_graph import TaxonomyGraph
from taxonomy.forms import (
    BreedForm,
    LLMTaxonomyCandidateGenerateForm,
    LLMTaxonomyCandidateMetadataForm,
    TaxonomyBreedCreateForm,
)
from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    LLMTaxonomyCandidate,
    LLMTaxonomyCandidateGenerationJob,
    Phylum,
    Species,
)


logger = logging.getLogger(__name__)


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

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "LLM生成候補を生成する権限がありません。")
            return redirect("txo:llm_candidate_list")

        pending_candidates = LLMTaxonomyCandidateRepository.pending_candidates()
        if pending_candidates:
            messages.info(
                request,
                "レビュー待ちのLLM生成候補があるため、新規生成せず既存候補を表示します。",
            )
            return redirect(self._preview_url(pending_candidates))

        try:
            job = LLMTaxonomyCandidateGenerationService.start_job(request.user)
        except LLMTaxonomyCandidateGenerationError as error:
            messages.error(request, str(error))
            return redirect("txo:llm_candidate_list")

        messages.success(
            request,
            "LLM生成ジョブを開始しました。進捗を確認してください。",
        )
        return redirect(f"{reverse('txo:llm_candidate_list')}?job_id={job.pk}")

    def get_queryset(self):
        return LLMTaxonomyCandidate.objects.select_related(
            "approved_breed",
            "reviewed_by",
        ).order_by(
            Case(
                When(status=LLMTaxonomyCandidate.ReviewStatus.PENDING, then=Value(0)),
                When(status=LLMTaxonomyCandidate.ReviewStatus.APPROVED, then=Value(1)),
                When(status=LLMTaxonomyCandidate.ReviewStatus.REJECTED, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            "-created_at",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate_ids = self._get_candidate_ids()
        candidates = []
        if candidate_ids:
            candidates = list(
                LLMTaxonomyCandidate.objects.filter(pk__in=candidate_ids).order_by(
                    "created_at", "pk"
                )
            )
        context["preview_candidate_ids"] = ",".join(
            str(candidate.pk) for candidate in candidates
        )
        context["candidate_previews"] = [
            {
                "candidate": candidate,
                "metadata_form": LLMTaxonomyCandidateMetadataForm(instance=candidate),
            }
            for candidate in candidates
        ]
        context["has_pending_candidates"] = bool(
            LLMTaxonomyCandidateRepository.pending_candidates()
        )
        context["generation_job"] = self._get_generation_job()
        return context

    def _get_candidate_ids(self) -> list[int]:
        raw_ids = self.request.GET.get("candidate_ids", "")
        candidate_ids = []
        for raw_id in raw_ids.split(","):
            if raw_id.isdigit():
                candidate_ids.append(int(raw_id))
        return candidate_ids

    def _preview_url(self, candidates: list[LLMTaxonomyCandidate]) -> str:
        candidate_ids = ",".join(str(candidate.pk) for candidate in candidates)
        return f"{reverse('txo:llm_candidate_new')}?candidate_ids={candidate_ids}"

    def _get_generation_job(self) -> LLMTaxonomyCandidateGenerationJob | None:
        job_id = self.request.GET.get("job_id")
        if job_id and job_id.isdigit():
            try:
                return LLMTaxonomyCandidateRepository.get_generation_job(int(job_id))
            except ObjectDoesNotExist:
                return None
        return LLMTaxonomyCandidateRepository.latest_generation_job()


class LLMTaxonomyCandidateCreateView(FormView):
    """
    LLMで分類候補を生成し、プレビュー用に保存するビュー。
    """

    form_class = LLMTaxonomyCandidateGenerateForm
    template_name = "taxonomy/llm_candidate_form.html"

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            messages.error(self.request, "LLM生成候補を生成する権限がありません。")
            return redirect("txo:llm_candidate_list")

        try:
            job = LLMTaxonomyCandidateGenerationService.start_job(self.request.user)
        except LLMTaxonomyCandidateGenerationError as error:
            messages.error(self.request, str(error))
            return self.render_to_response(self.get_context_data(form=form))

        messages.success(
            self.request,
            "LLM生成ジョブを開始しました。進捗を確認してください。",
        )
        return redirect(f"{reverse('txo:llm_candidate_list')}?job_id={job.pk}")

    def form_invalid(self, form):
        messages.error(
            self.request, "生成できませんでした。入力内容を確認してください。"
        )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate_ids = self._get_candidate_ids()
        candidates = []
        if candidate_ids:
            candidates = list(
                LLMTaxonomyCandidate.objects.filter(pk__in=candidate_ids).order_by(
                    "created_at", "pk"
                )
            )
        context["generated_candidates"] = candidates
        context["preview_candidate_ids"] = ",".join(
            str(candidate.pk) for candidate in candidates
        )
        context["candidate_previews"] = [
            {
                "candidate": candidate,
                "metadata_form": LLMTaxonomyCandidateMetadataForm(instance=candidate),
            }
            for candidate in candidates
        ]
        return context

    def _get_candidate_ids(self) -> list[int]:
        raw_ids = self.request.GET.get("candidate_ids", "")
        candidate_ids = []
        for raw_id in raw_ids.split(","):
            if not raw_id.isdigit():
                continue
            candidate_ids.append(int(raw_id))
        return candidate_ids


class LLMTaxonomyCandidateApproveView(View):
    """
    LLM生成分類候補を承認し、確認済みtaxonomyデータへ登録するビュー。
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "LLM生成候補を承認する権限がありません。")
            return redirect("txo:llm_candidate_list")

        preview_url = self._get_preview_url(request, kwargs["pk"])
        try:
            candidate = LLMTaxonomyCandidateRepository.get_for_review(kwargs["pk"])
        except ObjectDoesNotExist:
            messages.error(request, "指定された候補が見つかりません。")
            return redirect("txo:llm_candidate_list")
        if candidate.status != LLMTaxonomyCandidate.ReviewStatus.PENDING:
            messages.error(request, "レビュー待ちではない候補は操作できません。")
            return redirect("txo:llm_candidate_list")

        if self._has_metadata_fields(request):
            form = LLMTaxonomyCandidateMetadataForm(request.POST, instance=candidate)
            if not form.is_valid():
                messages.error(request, "出典とメモを確認してください。")
                return redirect(preview_url)

            candidate = form.save(commit=False)
            LLMTaxonomyCandidateRepository.update_metadata(candidate)

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

    def _get_preview_url(self, request, candidate_id: int) -> str:
        candidate_ids = request.POST.get("candidate_ids") or str(candidate_id)
        return f"{reverse('txo:llm_candidate_new')}?candidate_ids={candidate_ids}"

    def _has_metadata_fields(self, request) -> bool:
        return any(
            field_name in request.POST
            for field_name in LLMTaxonomyCandidateMetadataForm.Meta.fields
        )


class LLMTaxonomyCandidateGenerationJobStepView(View):
    """
    LLM分類候補生成ジョブをポーリングごとに1ステップ進めるビュー。
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return JsonResponse(
                {"error": "LLM生成候補を生成する権限がありません。"},
                status=403,
            )

        try:
            job = LLMTaxonomyCandidateRepository.get_generation_job(kwargs["pk"])
        except ObjectDoesNotExist:
            return JsonResponse({"error": "生成ジョブが見つかりません。"}, status=404)

        if job.status in [
            LLMTaxonomyCandidateGenerationJob.JobStatus.COMPLETED,
            LLMTaxonomyCandidateGenerationJob.JobStatus.FAILED,
        ]:
            return JsonResponse(self._job_payload(job))

        processing_job = (
            LLMTaxonomyCandidateRepository.acquire_generation_job_processing(
                job.pk,
                request.user,
                self._processing_token(),
            )
        )
        if processing_job is None:
            job = LLMTaxonomyCandidateRepository.get_generation_job(job.pk)
            return JsonResponse(self._job_payload(job))

        self._log_stale_processing_reacquired(job, request.user)
        job = processing_job
        try:
            job = LLMTaxonomyCandidateGenerationService.process_next_job_step(
                processing_job
            )
        finally:
            LLMTaxonomyCandidateRepository.release_generation_job_processing(job)

        return JsonResponse(self._job_payload(job))

    def _job_payload(self, job: LLMTaxonomyCandidateGenerationJob) -> dict:
        preview_url = ""
        if job.candidate_ids:
            candidate_ids = ",".join(
                str(candidate_id) for candidate_id in job.candidate_ids
            )
            preview_url = (
                f"{reverse('txo:llm_candidate_new')}?candidate_ids={candidate_ids}"
            )
        processing_message = self._processing_message(job)
        return {
            "id": job.pk,
            "status": job.status,
            "status_label": job.get_status_display(),
            "is_processing": job.is_processing,
            "processing_message": processing_message,
            "current_step": job.current_step,
            "current_target": job.current_target,
            "total_count": job.total_count,
            "processed_count": job.processed_count,
            "success_count": job.success_count,
            "failed_count": job.failed_count,
            "failures": job.failures,
            "error_message": job.error_message,
            "preview_url": preview_url,
            "is_finished": job.status
            in [
                LLMTaxonomyCandidateGenerationJob.JobStatus.COMPLETED,
                LLMTaxonomyCandidateGenerationJob.JobStatus.FAILED,
            ],
        }

    def _processing_message(self, job: LLMTaxonomyCandidateGenerationJob) -> str:
        if not job.is_processing:
            return ""

        actor = ""
        if (
            job.processing_by_id
            and self.request.user.is_authenticated
            and job.processing_by_id != self.request.user.pk
        ):
            actor = "別の管理者が"

        if job.total_count:
            processing_count = min(job.processed_count + 1, job.total_count)
            target = job.current_target or "対象未設定"
            return (
                f"{actor}生成ジョブの{job.total_count}件中"
                f"{processing_count}件目（{target}）を処理中です。"
            )

        step = job.current_step or "生成対象リスト作成"
        return f"{actor}生成ジョブの{step}を処理中です。"

    def _processing_token(self) -> str:
        return self.request.headers.get("X-Generation-Tab-Id", "")[:100]

    def _log_stale_processing_reacquired(
        self,
        previous_job: LLMTaxonomyCandidateGenerationJob,
        reacquired_by,
    ) -> None:
        stale_threshold = timezone.now() - timedelta(minutes=5)
        if (
            not previous_job.is_processing
            or previous_job.processing_started_at is None
            or previous_job.processing_started_at >= stale_threshold
        ):
            return

        logger.warning(
            "LLM分類候補生成ジョブのstale processing lockを再取得しました。",
            extra={
                "job_id": previous_job.pk,
                "processing_started_at": previous_job.processing_started_at.isoformat(),
                "previous_processing_by_id": previous_job.processing_by_id,
                "reacquired_by_id": getattr(reacquired_by, "pk", None),
                "reacquired_by_username": getattr(reacquired_by, "username", ""),
            },
        )


class LLMTaxonomyCandidateBulkApproveView(View):
    """
    表示中のLLM生成分類候補をまとめて確認済みtaxonomyデータへ登録するビュー。
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "LLM生成候補を承認する権限がありません。")
            return redirect("txo:llm_candidate_list")

        candidate_ids = self._get_candidate_ids(request)
        if not candidate_ids:
            messages.error(request, "登録対象のLLM生成候補がありません。")
            return redirect("txo:llm_candidate_list")

        try:
            breeds = LLMTaxonomyCandidateReviewService.approve_many(
                candidate_ids,
                request.user,
            )
        except LLMTaxonomyCandidateReviewError as error:
            messages.error(request, str(error))
            return redirect(self._get_preview_url(candidate_ids))

        messages.success(
            request,
            f"{len(breeds)}件のLLM生成候補を確認済みtaxonomyデータとして登録しました。",
        )
        return redirect("txo:llm_candidate_list")

    def _get_candidate_ids(self, request) -> list[int]:
        candidate_ids = []
        for raw_id in request.POST.get("candidate_ids", "").split(","):
            if raw_id.isdigit():
                candidate_ids.append(int(raw_id))
        return candidate_ids

    def _get_preview_url(self, candidate_ids: list[int]) -> str:
        joined_ids = ",".join(str(candidate_id) for candidate_id in candidate_ids)
        return f"{reverse('txo:llm_candidate_new')}?candidate_ids={joined_ids}"


class LLMTaxonomyCandidateBulkRejectView(View):
    """
    表示中のLLM生成分類候補をまとめて却下します。
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "LLM生成候補を却下する権限がありません。")
            return redirect("txo:llm_candidate_list")

        candidate_ids = self._get_candidate_ids(request)
        if not candidate_ids:
            messages.error(request, "却下対象のLLM生成候補がありません。")
            return redirect("txo:llm_candidate_list")

        try:
            rejected_count = LLMTaxonomyCandidateReviewService.reject_many(
                candidate_ids,
                request.user,
            )
        except LLMTaxonomyCandidateReviewError as error:
            messages.error(request, str(error))
            return redirect(self._get_preview_url(candidate_ids))

        messages.success(request, f"{rejected_count}件のLLM生成候補を却下しました。")
        return redirect("txo:llm_candidate_list")

    def _get_candidate_ids(self, request) -> list[int]:
        candidate_ids = []
        for raw_id in request.POST.get("candidate_ids", "").split(","):
            if raw_id.isdigit():
                candidate_ids.append(int(raw_id))
        return candidate_ids

    def _get_preview_url(self, candidate_ids: list[int]) -> str:
        joined_ids = ",".join(str(candidate_id) for candidate_id in candidate_ids)
        return f"{reverse('txo:llm_candidate_new')}?candidate_ids={joined_ids}"


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
