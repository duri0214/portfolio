import calendar
from datetime import date

from django.contrib import messages
from django.core.management import call_command
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, CreateView

from .domain.repository.facility_repository import FacilityRepository
from .forms import FacilityAvailabilityForm
from .models import Facility, FacilityAvailability


class IndexView(TemplateView):
    """トップページビュー"""

    template_name = "welfare_services/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 施設データの統計情報
        context["facilities_count"] = FacilityRepository.get_facilities_count()

        # 最終更新日時
        last_updated_facility = FacilityRepository.get_last_updated_facility()
        context["last_updated"] = (
            last_updated_facility.updated_at
            if last_updated_facility
            else timezone.now()
        )

        # 最近更新された施設と空き状況
        recent_facilities = FacilityRepository.get_recent_facilities()

        # 各施設の最新の空き状況情報を取得
        for facility in recent_facilities:
            # 最新の空き状況を取得
            latest_availability = FacilityRepository.get_latest_availability(facility)

            # 過去3ヶ月分の空き状況履歴を取得
            availability_history = FacilityRepository.get_facility_availabilities(
                facility
            )[:3]

            # 施設オブジェクトに情報を追加
            facility.latest_availability = latest_availability
            facility.availability_history = availability_history

        context["recent_facilities"] = recent_facilities

        return context


class FetchFacilitiesView(View):
    """APIから施設データを取得するビュー"""

    @staticmethod
    def post(request):
        try:
            # 管理コマンドを実行
            call_command("fetch_facilities")
            messages.success(request, "福祉事務所データの取得に成功しました！")
        except Exception as e:
            messages.error(request, f"データ取得中にエラーが発生しました: {str(e)}")

        # トップページにリダイレクト
        return HttpResponseRedirect(reverse("welf:index"))


class FacilityAvailabilityCreateView(CreateView):
    """福祉事務所の空き状況入力フォームビュー"""

    model = FacilityAvailability
    form_class = FacilityAvailabilityForm
    template_name = "welfare_services/facility_availability/form.html"
    success_url = reverse_lazy("welf:facility_availability_complete")

    def form_valid(self, form):
        # フォームから施設と年月を取得
        facility = form.cleaned_data.get("facility")
        year_month = form.cleaned_data.get("year_month")
        year, month = year_month.split("-")

        year = int(year)
        month = int(month)
        last_day = calendar.monthrange(year, month)[1]
        target_date = date(year, month, last_day)

        # 同じ施設・同じ年月のデータがすでに存在するか確認
        existing = FacilityAvailability.objects.filter(
            facility=facility, target_date=target_date
        ).first()

        if existing:
            # 既存データを更新する場合
            existing.available_count = form.cleaned_data.get("available_count")
            existing.remarks = form.cleaned_data.get("remarks")

            # 空き人数に応じてステータスを設定
            available_count = form.cleaned_data.get("available_count", 0)
            if available_count == 0:
                existing.status = "unavailable"
            elif 1 <= available_count <= 3:
                existing.status = "limited"
            else:
                existing.status = "available"

            existing.save()
            self.object = existing  # CreateViewでも既存オブジェクトを返す
            messages.success(
                self.request, "空き状況を更新しました。ご協力ありがとうございます。"
            )
        else:
            # 新規データを作成する場合
            messages.success(
                self.request, "空き状況を新規登録しました。ご協力ありがとうございます。"
            )
            return super().form_valid(form)

        return HttpResponseRedirect(self.get_success_url())


class FacilityAvailabilityCompleteView(TemplateView):
    """福祉事務所の空き状況入力完了ページビュー"""

    template_name = "welfare_services/facility_availability/complete.html"


class FacilityListView(TemplateView):
    """福祉事務所一覧ページビュー"""

    template_name = "welfare_services/facility/list.html"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # クエリパラメータを取得
        name = self.request.GET.get("name", "")
        area = self.request.GET.get("area", "")
        status = self.request.GET.get("status", "")

        # リポジトリを使用してフィルタリングされた施設を取得
        filtered_facilities = FacilityRepository.get_facilities_with_filter(name, area)

        # リポジトリを使用して空き状況でソートされた施設を取得
        facilities = FacilityRepository.get_sorted_facilities_by_availability(
            filtered_facilities, status
        )

        # ページネーション
        page = self.request.GET.get("page", 1)
        paginator = Paginator(facilities, self.paginate_by)
        try:
            facilities = paginator.page(page)
        except PageNotAnInteger:
            facilities = paginator.page(1)
        except EmptyPage:
            facilities = paginator.page(paginator.num_pages)

        # エリア選択肢を作成（例えば、区ごとのリスト）
        areas = [
            "千代田区",
            "中央区",
            "港区",
            "新宿区",
            "文京区",
            "台東区",
            "墨田区",
            "江東区",
            "品川区",
            "目黒区",
            "大田区",
            "世田谷区",
            "渋谷区",
            "中野区",
            "杉並区",
            "豊島区",
            "北区",
            "荒川区",
            "板橋区",
            "練馬区",
            "足立区",
            "葛飾区",
            "江戸川区",
        ]

        # 検索結果の総数とすべての施設数を追加
        context["total_count"] = paginator.count
        context["all_facilities_count"] = FacilityRepository.get_facilities_count()

        context["facilities"] = facilities
        context["paginator"] = paginator
        context["areas"] = areas
        return context


class FacilityDetailView(TemplateView):
    """福祉事務所詳細ページビュー"""

    template_name = "welfare_services/facility/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # URLから施設IDを取得
        facility_id = self.kwargs.get("pk")
        facility = get_object_or_404(Facility, id=facility_id)

        # リポジトリを使用して施設の空き状況履歴を取得
        availabilities = FacilityRepository.get_facility_availabilities(facility)

        # リポジトリを使用して最新の空き状況を取得
        latest_availability = FacilityRepository.get_latest_availability(facility)

        # テンプレート変数を設定
        facility.latest_availability = latest_availability

        # レビューデータを取得
        from django.db.models import Count, Avg
        from .models import FacilityReview

        # 承認済みのレビューのみ取得
        reviews = FacilityReview.objects.filter(
            facility=facility, is_approved=True
        ).order_by("-created_at")

        # 平均評価を計算
        average_rating = reviews.aggregate(Avg("rating"))["rating__avg"] or 0
        average_rating_rounded = int(average_rating)

        # 評価ごとの件数と割合を計算
        rating_counts = (
            reviews.values("rating").annotate(count=Count("rating")).order_by("rating")
        )
        rating_distribution = []
        total_reviews = reviews.count()

        for i in range(1, 6):  # 1-5の評価それぞれに対して
            count = next(
                (item["count"] for item in rating_counts if item["rating"] == i), 0
            )
            percentage = (count / total_reviews * 100) if total_reviews > 0 else 0
            rating_distribution.append(
                {"rating": i, "count": count, "percentage": percentage}
            )

        # リレーションフィールドには直接代入できないので、コンテキストに渡す
        context["facility"] = facility
        context["availabilities"] = availabilities
        context["reviews"] = reviews
        context["average_rating"] = average_rating
        context["average_rating_rounded"] = average_rating_rounded
        context["rating_distribution"] = rating_distribution
        return context
