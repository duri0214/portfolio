from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Count, Max, Min, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView

from .domain.repository.scenario_repository import ScenarioRepository
from .domain.service.meeting_index import MeetingIndexService
from .domain.service.pipeline import KokkaiPipeline
from .domain.service.scenario import ScenarioGenerationError, ScenarioService
from .domain.service.scenario_play import ScenarioPlayError, ScenarioPlayService
from .domain.valueobject.meeting import MEETING_METADATA_SPEAKER_NAME
from .models import Meeting


class IndexView(ListView):
    model = Meeting
    template_name = "kokkai/index.html"
    context_object_name = "meetings_by_date"
    PAGE_SIZE_OPTIONS = (30, 60, 120)
    DEFAULT_PAGE_SIZE = 30

    def get_queryset(self):
        start_date, end_date = self._get_display_period()
        return (
            Meeting.objects.filter(meeting_date__range=(start_date, end_date))
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
        start_date, end_date = self._get_display_period()
        context["start_date"] = start_date
        context["end_date"] = end_date
        context["page_size"] = self._get_page_size()
        context["page_size_options"] = self.PAGE_SIZE_OPTIONS
        context["period_query"] = self._build_period_query(start_date, end_date)
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
        if action == "create_index":
            indexed_count = MeetingIndexService().create_index(start_date, end_date)
            if not indexed_count:
                messages.info(
                    request,
                    "指定期間に議事録はありません。期間を変更して再度お試しください。",
                )
        elif action == "fetch_selected":
            meeting_ids = request.POST.getlist("meeting_ids")
            if not meeting_ids:
                messages.warning(request, "全文を取得する会議録を選択してください。")
            else:
                imported_count = KokkaiPipeline().import_selected_meetings(meeting_ids)
                messages.success(
                    request, f"{imported_count}件の会議録本文を取得しました。"
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

    def _get_display_period(self):
        if self.request.GET.get("start_date") or self.request.GET.get("end_date"):
            return self._get_period(self.request.GET)

        saved_range = Meeting.objects.aggregate(
            first_date=Min("meeting_date"), last_date=Max("meeting_date")
        )
        if saved_range["first_date"] and saved_range["last_date"]:
            return saved_range["first_date"], saved_range["last_date"]
        return self._get_period(self.request.GET)

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
        start_date, end_date = cls._get_period(values)
        return cls._build_period_query(start_date, end_date)


class MeetingDetailView(DetailView):
    model = Meeting
    template_name = "kokkai/meeting_detail.html"
    context_object_name = "meeting"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["speeches"] = self.object.speeches.exclude(
            speaker_name=MEETING_METADATA_SPEAKER_NAME
        ).order_by("speech_order")
        context["has_speeches"] = context["speeches"].exists()
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
        self.object = play
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
        context["current_choices"] = (
            list(current_turn.choices.all()) if current_turn is not None else []
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
