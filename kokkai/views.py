from django.views.generic import ListView, DetailView
from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponse
from datetime import datetime, timedelta
from .models import Meeting
from .domain.service.pipeline import KokkaiPipeline


class IndexView(ListView):
    model = Meeting
    template_name = "kokkai/index.html"
    context_object_name = "meetings_by_date"

    def get_queryset(self):
        # 日付ごとのグループ化はテンプレートで行うか、ここで加工する
        # ここでは単純に全件取得してテンプレート側で調整しやすくする（本来は集計したいが、一旦全件）
        return Meeting.objects.all().order_by("-meeting_date", "committee")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)

        # クエリパラメータがあればそれを使用
        start_date_str = self.request.GET.get("start_date")
        end_date_str = self.request.GET.get("end_date")

        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        context["start_date"] = start_date
        context["end_date"] = end_date
        return context

    @staticmethod
    def post(request, *args, **kwargs):
        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")

        if not start_date_str or not end_date_str:
            return redirect("kokkai:index")

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        pipeline = KokkaiPipeline()
        pipeline.process_and_save_meetings(start_date, end_date)

        return redirect(
            f"{reverse('kokkai:index')}?start_date={start_date_str}&end_date={end_date_str}"
        )


class MeetingDetailView(DetailView):
    model = Meeting
    template_name = "kokkai/meeting_detail.html"
    context_object_name = "meeting"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["speeches"] = self.object.speeches.all().order_by("speech_order")
        return context


def download_markdown(request):
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    query = Meeting.objects.values("meeting_date").distinct()
    if start_date_str:
        query = query.filter(meeting_date__gte=start_date_str)
    if end_date_str:
        query = query.filter(meeting_date__lte=end_date_str)

    content = ""
    for m in query:
        date_str = m["meeting_date"].strftime("%Y-%m-%d")
        # countの代わりに議題数を出すなどの変更が考えられるが、一旦日付のみ
        content += f"{date_str}\n"

    response = HttpResponse(content, content_type="text/markdown")
    response["Content-Disposition"] = 'attachment; filename="meeting_index.md"'
    return response
