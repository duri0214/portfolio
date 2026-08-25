from datetime import datetime, timedelta

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView

from .domain.service.meeting_index import MeetingIndexService
from .domain.service.pipeline import KokkaiPipeline
from .models import Meeting


class IndexView(ListView):
    model = Meeting
    template_name = "kokkai/index.html"
    context_object_name = "meetings_by_date"

    def get_queryset(self):
        start_date, end_date = self._get_period(self.request.GET)
        return (
            Meeting.objects.filter(meeting_date__range=(start_date, end_date))
            .annotate(speech_count=Count("speeches"))
            .order_by("-meeting_date", "committee", "meeting_number")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date = self._get_period(self.request.GET)
        context["start_date"] = start_date
        context["end_date"] = end_date
        context["has_meetings"] = context["meetings_by_date"].exists()
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


class MeetingDetailView(DetailView):
    model = Meeting
    template_name = "kokkai/meeting_detail.html"
    context_object_name = "meeting"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["speeches"] = self.object.speeches.all().order_by("speech_order")
        context["has_speeches"] = context["speeches"].exists()
        return context


def download_markdown(request):
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    query = Meeting.objects.all().order_by(
        "meeting_date", "committee", "meeting_number"
    )
    if start_date_str:
        query = query.filter(meeting_date__gte=start_date_str)
    if end_date_str:
        query = query.filter(meeting_date__lte=end_date_str)

    content = "\n".join(
        f"- {meeting.meeting_date:%Y-%m-%d} | {meeting.house} | "
        f"{meeting.committee} {meeting.meeting_number} | {meeting.min_id} | "
        f"{meeting.url}"
        for meeting in query
    )
    if content:
        content += "\n"

    response = HttpResponse(content, content_type="text/markdown")
    response["Content-Disposition"] = 'attachment; filename="meeting_index.md"'
    return response
