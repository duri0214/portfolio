from django.views.generic import ListView
from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponse
from datetime import datetime, timedelta
from .models import MeetingIndex
from .domain.service.kokkai_api import KokkaiAPIClient


class IndexView(ListView):
    model = MeetingIndex
    template_name = "kokkai/index.html"
    context_object_name = "meetings"

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

        client = KokkaiAPIClient()
        counts = client.get_meeting_counts_by_date(start_date, end_date)

        for date_str, count in counts.items():
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            MeetingIndex.objects.update_or_create(date=dt, defaults={"count": count})

        return redirect(
            f"{reverse('kokkai:index')}?start_date={start_date_str}&end_date={end_date_str}"
        )


def download_markdown(request):
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    query = MeetingIndex.objects.all()
    if start_date_str:
        query = query.filter(date__gte=start_date_str)
    if end_date_str:
        query = query.filter(date__lte=end_date_str)

    content = ""
    for m in query:
        date_str = m.date.strftime("%Y-%m-%d")
        url = f"https://kokkai.ndl.go.jp/#/result?from={date_str}&until={date_str}"
        content += f"[{m.date}]({url}) : {m.count}件\n"

    response = HttpResponse(content, content_type="text/markdown")
    response["Content-Disposition"] = 'attachment; filename="meeting_index.md"'
    return response
