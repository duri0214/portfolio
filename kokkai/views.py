import base64
import binascii
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

import requests
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from .domain.repository.scenario_repository import ScenarioRepository
from .domain.service.affiliation_import import AffiliationImportService
from .domain.service.affiliation_timeline import AffiliationTimelineService
from .domain.service.meeting_catalog import MeetingCatalogService
from .domain.service.pipeline import KokkaiPipeline
from .domain.service.participant_query import ParticipantQueryService
from .domain.service.reading_support import ReadingSupportService
from .domain.service.reading_support_candidates import ReadingSupportCandidateService
from .domain.service.reading_support_import import ReadingSupportCsvImporter
from .domain.service.scenario import ScenarioGenerationError, ScenarioService
from .domain.service.scenario_play import ScenarioPlayError, ScenarioPlayService
from .domain.valueobject.meeting import MEETING_METADATA_SPEAKER_NAME
from .forms import (
    ReadingSupportCsvImportForm,
    ReadingSupportEntryForm,
)
from .models import AffiliationImportJob, Meeting, ObservedPerson, ReadingSupportEntry


class KokkaiManagementRequiredMixin(UserPassesTestMixin):
    """KOKKAI内の管理機能をスーパーユーザーだけに許可するMixin。"""

    raise_exception = True

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class PageSizePaginationMixin:
    """30、60、120件から選ぶ一覧ページの共通ページング設定。"""

    PAGE_SIZE_OPTIONS = (30, 60, 120)
    DEFAULT_PAGE_SIZE = 30

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_size"] = self._get_page_size()
        context["page_size_options"] = self.PAGE_SIZE_OPTIONS
        return context

    def get_paginate_by(self, queryset):
        return self._get_page_size()

    def _get_page_size(self):
        try:
            page_size = int(self.request.GET.get("page_size", self.DEFAULT_PAGE_SIZE))
        except (TypeError, ValueError):
            return self.DEFAULT_PAGE_SIZE
        return (
            page_size if page_size in self.PAGE_SIZE_OPTIONS else self.DEFAULT_PAGE_SIZE
        )


class IndexView(PageSizePaginationMixin, ListView):
    model = Meeting
    template_name = "kokkai/index.html"
    context_object_name = "meetings_by_date"

    def get_queryset(self):
        return (
            Meeting.objects.all()
            .annotate(
                speech_count=Count(
                    "speeches",
                    filter=~Q(speeches__speaker_name=MEETING_METADATA_SPEAKER_NAME),
                )
            )
            .order_by("-meeting_date", "committee", "meeting_number")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date = self._get_period(self.request.GET)
        context["start_date"] = start_date
        context["end_date"] = end_date
        context["period_query"] = self._period_query(self.request.GET)
        context["can_manage_reading_support"] = (
            self.request.user.is_authenticated and self.request.user.is_superuser
        )
        return context

    @staticmethod
    def post(request, *args, **kwargs):
        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")

        if not start_date_str or not end_date_str:
            messages.error(request, "開始日と終了日を指定してください。")
            return redirect("kokkai:index")

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "日付の形式が正しくありません。")
            return redirect("kokkai:index")

        action = request.POST.get("action")
        if action == "rebuild_meeting_catalog":
            catalog_count = MeetingCatalogService().rebuild_meeting_catalog(
                start_date, end_date
            )
            if not catalog_count:
                messages.info(
                    request,
                    "指定期間に議事録はありません。期間を変更して再度お試しください。",
                )
        elif action == "fetch_selected":
            meeting_ids = request.POST.getlist("meeting_ids")
            if not meeting_ids:
                messages.warning(
                    request, "本文をデータベースに取り込む会議録を選択してください。"
                )
            else:
                imported_count = KokkaiPipeline().import_selected_meetings(meeting_ids)
                messages.success(
                    request,
                    f"{imported_count}件の会議録本文をデータベースに取り込みました。",
                )
        else:
            messages.error(request, "実行内容を選択してください。")

        return redirect(
            f"{reverse('kokkai:index')}?start_date={start_date_str}&end_date={end_date_str}"
        )

    @staticmethod
    def _get_period(values):
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        start_date_str = values.get("start_date")
        end_date_str = values.get("end_date")

        try:
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
        return start_date, end_date

    @staticmethod
    def _build_period_query(start_date, end_date):
        return urlencode(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        )

    @classmethod
    def _period_query(cls, values):
        if not values.get("start_date") and not values.get("end_date"):
            return ""
        start_date, end_date = cls._get_period(values)
        return cls._build_period_query(start_date, end_date)


class AffiliationTraceabilityView(TemplateView):
    """
    会派観測の期間取得と人物一覧を、ロープレから独立して表示する。

    Attributes:
        DEFAULT_YEARS_BACK: 初期表示で今日から遡る年数。
        CHART_PAGE_SIZE: 一度に描画するガントチャートの人物数。
    """

    template_name = "kokkai/politician_list.html"
    DEFAULT_YEARS_BACK = 10
    CHART_PAGE_SIZE = 100

    def get_template_names(self):
        if self.request.GET.get("chart_only") == "1":
            return ["kokkai/affiliation_chart.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chart_page = self._chart_page()
        context["chart"] = AffiliationTimelineService().get_chart(
            offset=(chart_page - 1) * self.CHART_PAGE_SIZE,
            limit=self.CHART_PAGE_SIZE,
            query=self.request.GET.get("q", "").strip(),
        )
        context["chart_query"] = self.request.GET.get("q", "").strip()
        context["chart_page"] = chart_page
        context["chart_page_size"] = self.CHART_PAGE_SIZE
        context["chart_has_previous"] = chart_page > 1
        context["chart_has_next"] = bool(
            context["chart"]
            and context["chart"].total_row_count > chart_page * self.CHART_PAGE_SIZE
        )
        today = date.today()
        context["default_start_date"] = self._years_ago(today, self.DEFAULT_YEARS_BACK)
        context["default_end_date"] = today
        context["import_job"] = AffiliationImportJob.objects.filter(
            pk=self.request.GET.get("import_job")
        ).first()
        return context

    def _chart_page(self) -> int:
        """クエリ文字列から会派ガントチャートのページ番号を取得する。"""

        try:
            return max(int(self.request.GET.get("chart_page", "1")), 1)
        except ValueError:
            return 1

    def post(self, request, *args, **kwargs):
        try:
            start_date = date.fromisoformat(request.POST["start_date"])
            end_date = date.fromisoformat(request.POST["end_date"])
        except (KeyError, ValueError):
            messages.error(request, "開始日と終了日を正しい形式で指定してください。")
            return redirect("kokkai:affiliation_traceability")
        if end_date < start_date:
            messages.error(request, "終了日は開始日以降にしてください。")
            return redirect("kokkai:affiliation_traceability")

        current_end_date = AffiliationImportService.first_chunk_end(
            start_date, end_date
        )
        job = AffiliationImportJob.objects.create(
            start_date=start_date,
            end_date=end_date,
            current_start_date=start_date,
            current_end_date=current_end_date,
        )
        messages.success(
            request,
            "会派観測の非同期取得を開始しました。画面を開いたままお待ちください。",
        )
        return redirect(
            f"{reverse('kokkai:affiliation_traceability')}?import_job={job.pk}"
        )

    @staticmethod
    def _years_ago(today: date, years: int) -> date:
        """うるう日を含め、今日から指定年数前の日付を返す。"""

        try:
            return today.replace(year=today.year - years)
        except ValueError:
            return today.replace(year=today.year - years, day=28)


class AffiliationImportStepView(View):
    """会派観測取得処理を一つのAPIページずつ進め、JSONで進捗を返す。"""

    def post(self, request, pk, *args, **kwargs):
        job = get_object_or_404(AffiliationImportJob, pk=pk)
        if job.status == AffiliationImportJob.Status.COMPLETED:
            return JsonResponse(self._payload(job))

        job.status = AffiliationImportJob.Status.RUNNING
        job.error_message = ""
        job.save(update_fields=["status", "error_message", "updated_at"])
        try:
            result = AffiliationImportService().import_page(
                job.current_start_date,
                job.current_end_date,
                job.next_record_position,
            )
        except requests.RequestException:
            job.status = AffiliationImportJob.Status.FAILED
            job.error_message = (
                "国会会議録APIとの通信がタイムアウトしました。再開できます。"
            )
            job.save(update_fields=["status", "error_message", "updated_at"])
            return JsonResponse(self._payload(job), status=503)

        job.processed_meeting_count += result.meeting_count
        job.current_period_record_count = result.total_meeting_count
        if (
            result.next_record_position
            and result.next_record_position > job.next_record_position
        ):
            job.next_record_position = result.next_record_position
        elif job.current_end_date >= job.end_date:
            job.status = AffiliationImportJob.Status.COMPLETED
        else:
            next_start_date = job.current_end_date + timedelta(days=1)
            job.current_start_date = next_start_date
            job.current_end_date = AffiliationImportService.first_chunk_end(
                next_start_date, job.end_date
            )
            job.next_record_position = 1
            job.current_period_record_count = None
        job.save()
        return JsonResponse(self._payload(job))

    @staticmethod
    def _payload(job: AffiliationImportJob) -> dict[str, str | int | None]:
        """ブラウザーで次の取得要求を判断できる進捗情報を組み立てる。"""

        return {
            "status": job.status,
            "processed_meeting_count": job.processed_meeting_count,
            "current_start_date": job.current_start_date.isoformat(),
            "current_end_date": job.current_end_date.isoformat(),
            "current_period_record_count": job.current_period_record_count,
            "error_message": job.error_message or None,
        }


class PoliticianTimelineView(DetailView):
    """観測対象の全区間、またはバーに対応する一区間の根拠を表示する。"""

    model = ObservedPerson
    template_name = "kokkai/politician_timeline.html"
    context_object_name = "person"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        summary, periods = AffiliationTimelineService().get_timeline(self.object)
        context["summary"] = summary
        selected_id = self.request.GET.get("period")
        if selected_id is not None:
            selected_periods = [
                period
                for period in periods
                if str(period.first_observation_id) == selected_id
            ]
            context["focused_period"] = bool(selected_periods)
            context["missing_period"] = not selected_periods
            if selected_periods:
                periods = selected_periods
        context["periods"] = periods
        return context


class ReadingSupportManagementView(
    PageSizePaginationMixin,
    KokkaiManagementRequiredMixin,
    ListView,
):
    """KOKKAI内の読み仮名支援辞書と辞書ビューアを表示する画面。"""

    model = ReadingSupportEntry
    template_name = "kokkai/reading_support/index.html"
    context_object_name = "entries"

    def get_queryset(self):
        return ReadingSupportEntry.objects.all().order_by("word", "pk")


class ReadingSupportEntryUpdateView(KokkaiManagementRequiredMixin, UpdateView):
    """KOKKAI内の読み仮名支援辞書エントリを編集する画面。"""

    model = ReadingSupportEntry
    form_class = ReadingSupportEntryForm
    template_name = "kokkai/reading_support/entry_form.html"
    success_url = reverse_lazy("kokkai:reading_support_management")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "辞書項目を更新しました。")
        return response


class ReadingSupportEntryDeleteView(KokkaiManagementRequiredMixin, DeleteView):
    """KOKKAI内の読み仮名支援辞書エントリを削除する画面。"""

    model = ReadingSupportEntry
    success_url = reverse_lazy("kokkai:reading_support_management")
    http_method_names = ["post", "options"]

    def form_valid(self, form):
        word = self.object.word
        response = super().form_valid(form)
        messages.success(self.request, f"辞書項目「{word}」を削除しました。")
        return response


class ReadingSupportCsvImportView(KokkaiManagementRequiredMixin, FormView):
    """KOKKAI内で辞書CSVを取り込み、または候補CSVを生成する画面。"""

    template_name = "kokkai/reading_support/csv_import.html"
    form_class = ReadingSupportCsvImportForm

    def post(self, request, *args, **kwargs):
        """プレビュー済み候補CSVのダウンロードはGPTとDBを呼ばない。"""
        if "candidate_csv" in request.POST:
            try:
                csv_content = base64.b64decode(
                    request.POST["candidate_csv"], validate=True
                ).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                return HttpResponse("CSVデータが正しくありません。", status=400)
            response = HttpResponse(
                "\ufeff" + csv_content, content_type="text/csv; charset=utf-8"
            )
            response["Content-Disposition"] = (
                'attachment; filename="reading-support-dictionary-candidates.csv"'
            )
            return response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        if form.cleaned_data["generate_candidates"]:
            result = ReadingSupportCandidateService().generate_csv(
                form.cleaned_data["file"].read()
            )
            if result.errors:
                return self.render_to_response(
                    self.get_context_data(form=form, candidate_result=result),
                    status=400,
                )
            candidate_csv = base64.b64encode(result.to_csv().encode("utf-8")).decode(
                "ascii"
            )
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    candidate_result=result,
                    candidate_csv=candidate_csv,
                ),
                status=502 if result.generation_failed else 200,
            )
        result = ReadingSupportCsvImporter().import_csv(
            form.cleaned_data["file"].read()
        )
        if result.is_success:
            messages.success(
                self.request,
                (
                    f"CSVを取り込みました（新規 {result.created}件、"
                    f"上書き {result.updated}件）。"
                ),
            )
            return redirect("kokkai:reading_support_management")
        return self.render_to_response(self.get_context_data(form=form, result=result))


class ReadingSupportCsvTemplateView(KokkaiManagementRequiredMixin, View):
    """読み仮名支援辞書へ入力するサンプル付きCSVテンプレートをダウンロードする。"""

    TEMPLATE_CONTENT = (
        "word,reading,description,source_url\r\n"
        "FOIP,フォイップ,Free and Open Indo-Pacific（自由で開かれたインド太平洋）の略称で、法の支配に基づく自由で開かれた地域の実現を目指す外交上の概念です。,https://www.meti.go.jp/policy/external_economy/trade/foip/index.html\r\n"
        "お諮り,おはかり,読み仮名を補正するための登録語です。,\r\n"
        "NISA,ニーサ,少額投資非課税制度です。,https://example.com/nisa\r\n"
    )

    def get(self, request, *args, **kwargs):
        response = HttpResponse(
            "\ufeff" + self.TEMPLATE_CONTENT,
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            'attachment; filename="reading-support-dictionary-template.csv"'
        )
        return response


class MeetingDetailView(DetailView):
    model = Meeting
    template_name = "kokkai/meeting_detail.html"
    context_object_name = "meeting"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["speeches"] = self.object.speeches.exclude(
            speaker_name=MEETING_METADATA_SPEAKER_NAME
        ).order_by("speech_order", "pk")
        context["has_speeches"] = context["speeches"].exists()
        reading_support = ReadingSupportService()
        context["speech_items"] = [
            {
                "speech": speech,
                "annotation": reading_support.annotate(speech.speech_text),
            }
            for speech in context["speeches"]
        ]
        participant_service = ParticipantQueryService()
        context["participants"] = participant_service.list_participants(self.object)
        context["participant_summary"] = participant_service.get_participant_summary(
            self.object
        )
        context["has_participants"] = (
            context["participant_summary"].attendance_count > 0
        )
        availability = ScenarioService().get_availability(self.object)
        context["scenario"] = availability.scenario
        context["scenario_needs_regeneration"] = availability.needs_regeneration
        context["index_query"] = IndexView._period_query(self.request.GET)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")
        service = ScenarioService()
        try:
            if action == "create_scenario":
                scenario, created = service.get_or_create(self.object)
                if created:
                    messages.success(request, "シナリオを作成しました。")
                else:
                    messages.info(request, "保存済みのシナリオを再利用します。")
            elif action == "regenerate_scenario":
                scenario = service.regenerate(self.object)
                messages.success(request, "新しいバージョンのシナリオを作成しました。")
            else:
                messages.error(request, "不正な操作です。")
                return redirect("kokkai:meeting_detail", pk=self.object.pk)
        except ScenarioGenerationError as error:
            messages.error(request, f"シナリオを作成できませんでした: {error}")
            return render(
                request,
                self.template_name,
                self.get_context_data(),
                status=error.status_code,
            )
        return redirect("kokkai:scenario_actor_select", scenario_id=scenario.pk)


class ScenarioActorSelectView(DetailView):
    """保存済みシナリオの担当アクターを選択する画面。"""

    template_name = "kokkai/scenario_actor_select.html"
    context_object_name = "scenario"

    def get_object(self, queryset=None):
        return ScenarioRepository().get_scenario(self.kwargs["scenario_id"])

    def post(self, request, *args, **kwargs):
        scenario = self.get_object()
        actor_id = request.POST.get("actor_id")
        try:
            play = ScenarioPlayService().start(scenario, int(actor_id))
        except (TypeError, ValueError):
            messages.error(request, "担当する登場アクターを選択してください。")
            return redirect("kokkai:scenario_actor_select", scenario_id=scenario.pk)
        return redirect("kokkai:scenario_game", play_id=play.play_id)


class ScenarioGameView(DetailView):
    """会議録の発言を順に表示し、担当アクターの発言だけ二択を遅延生成する画面。"""

    template_name = "kokkai/scenario_game.html"
    context_object_name = "play"

    def get_object(self, queryset=None):
        return ScenarioRepository().get_play(self.kwargs["play_id"])

    def get(self, request, *args, **kwargs):
        play = self.get_object()
        if play.is_completed:
            return redirect("kokkai:scenario_result", play_id=play.play_id)
        try:
            self.object = ScenarioPlayService().prepare_current_turn(str(play.play_id))
        except ScenarioGenerationError as error:
            messages.error(request, f"選択肢を生成できませんでした: {error}")
            self.object = play
            return render(
                request,
                self.template_name,
                self.get_context_data(),
                status=error.status_code,
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        turns = list(self.object.scenario.turns.all())
        current_turn = next(
            (
                turn
                for turn in turns
                if turn.turn_number == self.object.next_turn_number
            ),
            None,
        )
        next_turn = next(
            (
                turn
                for turn in turns
                if turn.turn_number == self.object.next_turn_number + 1
            ),
            None,
        )
        previous_turn = next(
            (
                turn
                for turn in turns
                if turn.turn_number == self.object.next_turn_number - 1
            ),
            None,
        )
        player_turns = [
            turn for turn in turns if turn.actor_id == self.object.selected_actor_id
        ]
        last_turn = turns[-1] if turns else None
        last_player_turn = player_turns[-1] if player_turns else None
        next_player_turn = next(
            (
                turn
                for turn in player_turns
                if turn.turn_number >= self.object.next_turn_number
            ),
            None,
        )
        context["completed_turns"] = [
            turn for turn in turns if turn.turn_number < self.object.next_turn_number
        ]
        context["total_turns"] = len(turns)
        context["turn_progress_percent"] = (
            min(100, int((self.object.next_turn_number - 1) / len(turns) * 100))
            if turns
            else 0
        )
        context["current_turn"] = current_turn
        reading_support = ReadingSupportService()
        annotation_by_turn_id = {
            turn.pk: reading_support.annotate(turn.dialogue)
            for turn in [*context["completed_turns"], current_turn]
            if turn is not None
        }
        context["current_turn_annotation"] = (
            annotation_by_turn_id.get(current_turn.pk)
            if current_turn is not None
            else None
        )
        context["previous_turn_annotation"] = (
            annotation_by_turn_id.get(previous_turn.pk)
            if previous_turn is not None
            else None
        )
        context["completed_turn_items"] = [
            {
                "turn": turn,
                "annotation": annotation_by_turn_id[turn.pk],
            }
            for turn in context["completed_turns"]
        ]
        context["previous_turn"] = previous_turn
        context["is_response_to_other_actor"] = (
            previous_turn is not None
            and previous_turn.actor_id != self.object.selected_actor_id
        )
        context["can_skip_to_before_player_turn"] = (
            current_turn is not None
            and current_turn.actor_id != self.object.selected_actor_id
            and next_player_turn is not None
            and next_player_turn.turn_number > self.object.next_turn_number + 1
        )
        context["can_skip_to_final_turn"] = (
            current_turn is not None
            and current_turn.actor_id != self.object.selected_actor_id
            and last_turn is not None
            and last_player_turn is not None
            and last_player_turn.turn_number < current_turn.turn_number
            and current_turn.turn_number < last_turn.turn_number
        )
        player_turn_markers = []
        for turn in player_turns:
            if turn.turn_number < self.object.next_turn_number:
                state = "is-completed"
            elif turn.turn_number == self.object.next_turn_number:
                state = "is-current"
            elif (
                next_player_turn is not None
                and turn.turn_number == next_player_turn.turn_number
            ):
                state = "is-next"
            else:
                state = "is-upcoming"
            player_turn_markers.append(
                {
                    "turn_number": turn.turn_number,
                    "position": round((turn.turn_number - 1) / len(turns) * 100, 2),
                    "state": state,
                }
            )
        context["player_turn_markers"] = player_turn_markers
        context["is_next_player_turn"] = (
            current_turn is not None
            and current_turn.actor_id != self.object.selected_actor_id
            and next_turn is not None
            and next_turn.actor_id == self.object.selected_actor_id
        )
        context["current_choices"] = (
            ScenarioRepository().get_turn_choices(
                current_turn,
                self.object,
                ScenarioService.CHOICE_PROMPT_VERSION,
            )
            if current_turn is not None
            else []
        )
        context["is_player_turn"] = (
            current_turn is not None
            and current_turn.actor_id == self.object.selected_actor_id
            and bool(context["current_choices"])
        )
        return context

    def post(self, request, *args, **kwargs):
        play = self.get_object()
        if play.is_completed:
            return redirect("kokkai:scenario_result", play_id=play.play_id)

        try:
            updated_play = ScenarioPlayService().progress(
                str(play.play_id),
                request.POST.get("action"),
                request.POST.get("choice_id"),
            )
        except ScenarioGenerationError as error:
            messages.error(request, f"選択肢を生成できませんでした: {error}")
            self.object = play
            return render(
                request,
                self.template_name,
                self.get_context_data(),
                status=error.status_code,
            )
        except ScenarioPlayError:
            messages.error(request, "選択肢を確認して、もう一度操作してください。")
            return redirect("kokkai:scenario_game", play_id=play.play_id)

        if updated_play.is_completed:
            return redirect("kokkai:scenario_result", play_id=play.play_id)
        return redirect("kokkai:scenario_game", play_id=play.play_id)


class ScenarioResultView(DetailView):
    """保存済み選択結果と根拠発言を表示する最終判定画面。"""

    template_name = "kokkai/scenario_result.html"
    context_object_name = "play"

    def get_object(self, queryset=None):
        return ScenarioRepository().get_play(self.kwargs["play_id"])

    def get(self, request, *args, **kwargs):
        play = self.get_object()
        if not play.is_completed:
            return redirect("kokkai:scenario_game", play_id=play.play_id)
        self.object = play
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["result_label"] = ScenarioPlayService.result_label_for(self.object)
        context["result_explanation"] = ScenarioPlayService.result_explanation_for(
            self.object
        )
        return context
