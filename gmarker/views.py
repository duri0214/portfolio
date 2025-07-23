import json
import os

from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.views.generic import TemplateView

from gmarker.domain.repository.google import NearbyPlaceRepository
from gmarker.domain.service.google import GoogleMapsService
from gmarker.forms import CoordinateForm
from lib.geo.valueobject.coord import GoogleMapsCoord


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

        # マップデータの設定
        context["map_data"] = json.dumps(
            {
                "center": {
                    "lat": center_lat,
                    "lng": center_lng,
                },
                "places": place_data,
            },
            ensure_ascii=False,
        )

        context["google_maps_fe_api_key"] = os.getenv("GOOGLE_MAPS_FE_API_KEY")
        context["places"] = place_data
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
        # 初期値として使用する緯度と経度を空で定義
        initial_data = {"latitude": "", "longitude": ""}

        # `category=9` の NearbyPlace を取得
        default_location = NearbyPlaceRepository.get_default_location()
        if default_location:
            # locationをカンマで分割し初期値として設定
            lat, lng = map(float, default_location.place.location.split(","))
            initial_data = {"latitude": lat, "longitude": lng}

        # フォームを初期値付きで作成
        form = CoordinateForm(initial=initial_data)
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        # フォームからのデータを処理
        form = CoordinateForm(request.POST)
        if form.is_valid():
            # フォームの緯度・経度データを取得
            latitude = form.cleaned_data["latitude"]
            longitude = form.cleaned_data["longitude"]

            # GoogleMapsCoordクラスで処理
            coord = GoogleMapsCoord(latitude, longitude)

            # リポジトリを利用してアップサート処理
            nearby_place = NearbyPlaceRepository.upsert_default_location(coord)
            if nearby_place:
                print(f"upsert NearbyPlace: {nearby_place.place.location}")

            # 正常終了後、リダイレクト
            return redirect(reverse("mrk:index"))

        # フォームエラー時、再表示
        return render(request, self.template_name, {"form": form})
