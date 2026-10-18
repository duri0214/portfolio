import json
import logging
import os

from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView

from gmarker.domain.repository.google import NearbyPlaceRepository
from gmarker.domain.service.google import GoogleMapsService
from gmarker.domain.service.place_candidate_filter import (
    CriteriaNotFoundError,
    FIELD_MASK_WITH_REVIEWS,
    PlaceCandidateFilter,
    PlacesApiClient,
    PlacesApiError,
    PlaceSearchCriteriaCatalog,
    RequiredPlaceMissingError,
)
from gmarker.forms import CoordinateForm
from lib.geo.valueobject.coord import GoogleMapsCoord


logger = logging.getLogger(__name__)


class IndexView(TemplateView):
    template_name = "gmarker/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_code = self.kwargs.get("search_code", 9)

        place_data = NearbyPlaceRepository.find_places_with_reviews_by_category(
            category=search_code, review_limit=5
        )

        map_center = NearbyPlaceRepository.get_default_location()
        center_lat, center_lng = map(float, map_center.place.location.split(","))

        context["map_data"] = json.dumps(
            {
                "center": {
                    "lat": center_lat,
                    "lng": center_lng,
                },
                "places": place_data,
                "mapId": os.getenv("GOOGLE_MAPS_MAP_ID", "8f6a4cf0806f4732"),
            },
            ensure_ascii=False,
        )
        context["google_maps_fe_api_key"] = os.getenv("GOOGLE_MAPS_FE_API_KEY")
        context["places"] = place_data
        context["candidate_profiles"] = (
            []
            if getattr(self, "skip_candidate_profiles", False)
            else PlaceSearchCriteriaCatalog().all()
        )
        return context

    @staticmethod
    def post(request, search_code: int):
        if search_code == NearbyPlaceRepository.CATEGORY_SEARCH:
            map_center = NearbyPlaceRepository.get_default_location()
            center_lat, center_lng = map(float, map_center.place.location.split(","))
            search_types = request.POST.get("search_types", "").split(",")

            if not search_types:
                return redirect(reverse("mrk:index"))

            service = GoogleMapsService(os.getenv("GOOGLE_MAPS_BE_API_KEY"))
            place_vo_list = service.nearby_search(
                center=GoogleMapsCoord(center_lat, center_lng),
                search_types=search_types,
                radius=1500,
                fields=[
                    "places.id",
                    "places.location",
                    "places.displayName.text",
                    "places.rating",
                    "places.reviews",
                ],
            )
            NearbyPlaceRepository.handle_search_code(
                category=NearbyPlaceRepository.CATEGORY_SEARCH,
                search_types=",".join(search_types),
                place_vo_list=place_vo_list,
            )
        return redirect(
            reverse_lazy("mrk:nearby_search", kwargs={"search_code": search_code})
        )


class CoordinateRegisterView(TemplateView):
    template_name = "gmarker/coord/create.html"

    def get(self, request, *args, **kwargs):
        initial_data = {"latitude": "", "longitude": ""}
        default_location = NearbyPlaceRepository.get_default_location()
        if default_location:
            lat, lng = map(float, default_location.place.location.split(","))
            initial_data = {"latitude": lat, "longitude": lng}

        form = CoordinateForm(initial=initial_data)
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        form = CoordinateForm(request.POST)
        if form.is_valid():
            coord = GoogleMapsCoord(
                form.cleaned_data["latitude"], form.cleaned_data["longitude"]
            )
            nearby_place = NearbyPlaceRepository.upsert_default_location(coord)
            if nearby_place:
                print(f"upsert NearbyPlace: {nearby_place.place.location}")
            return redirect(reverse("mrk:index"))

        return render(request, self.template_name, {"form": form})


class CandidateSearchView(IndexView):
    """criteria の slug を受け取り、候補店舗を地図とレビューで表示する。"""

    default_criteria_slug = None

    def get(self, request, criteria_slug=None, *args, **kwargs):
        return self._search(criteria_slug)

    def post(self, request, criteria_slug=None, *args, **kwargs):
        return self._search(criteria_slug)

    def _search(self, criteria_slug):
        slug = criteria_slug or self.default_criteria_slug
        try:
            criteria = PlaceSearchCriteriaCatalog().resolve(slug or "")
        except CriteriaNotFoundError:
            return self._render_error(
                "指定された候補検索プロファイルが見つかりません。", status=404
            )
        except ValueError:
            logger.exception("候補検索プロファイルの読み込みに失敗しました")
            return self._render_error(
                "候補検索プロファイルに問題があります。管理者へ連絡してください。",
                status=500,
            )

        api_key = os.getenv("GOOGLE_MAPS_BE_API_KEY")
        if not api_key:
            return self._render_error(
                "候補店舗を取得できません。サーバーの Google Maps API キー設定を確認してください。",
                status=503,
                criteria=criteria,
            )

        try:
            client = PlacesApiClient(api_key, field_mask=FIELD_MASK_WITH_REVIEWS)
            result = PlaceCandidateFilter(client).collect(
                criteria, include_reviews=True
            )
        except (PlacesApiError, RequiredPlaceMissingError):
            logger.exception("候補店舗の取得に失敗しました: %s", criteria.slug)
            return self._render_error(
                "候補店舗を取得できませんでした。時間を置いて再度実行してください。",
                status=502,
                criteria=criteria,
            )
        except ValueError:
            logger.exception(
                "候補検索プロファイルの処理に失敗しました: %s", criteria.slug
            )
            return self._render_error(
                "候補検索プロファイルに問題があります。管理者へ連絡してください。",
                status=500,
                criteria=criteria,
            )

        context = self.get_context_data()
        display_places = PlaceCandidateFilter.to_display_records(result["candidates"])
        context["places"] = display_places
        context["candidate_result"] = result
        context["selected_criteria"] = criteria
        context["map_data"] = json.dumps(
            {
                "center": {"lat": criteria.center_lat, "lng": criteria.center_lng},
                "places": display_places,
                "mapId": os.getenv("GOOGLE_MAPS_MAP_ID", "8f6a4cf0806f4732"),
            },
            ensure_ascii=False,
        )
        return self.render_to_response(context)

    def _render_error(self, message: str, *, status: int, criteria=None):
        """候補検索エラーを画面に表示し、HTTP エラーとして返す。"""
        try:
            context = self.get_context_data()
        except ValueError:
            logger.exception("候補検索エラー画面の criteria 一覧を読み込めません")
            self.skip_candidate_profiles = True
            try:
                context = self.get_context_data()
            finally:
                del self.skip_candidate_profiles
        if criteria is not None:
            context["selected_criteria"] = criteria
        context["candidate_error"] = message
        return self.render_to_response(context, status=status)
