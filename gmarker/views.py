import json
import os

from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.views.generic import TemplateView

from gmarker.domain.repository.googlemaps import NearbyPlaceRepository
from gmarker.domain.service.googlemaps import GoogleMapsService
from gmarker.forms import CoordinateForm
from lib.geo.valueobject.coords import GoogleMapCoords


class IndexView(TemplateView):
    template_name = "gmarker/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_code = self.kwargs.get("search_code", 9)
        nearby_places = NearbyPlaceRepository.find_by_category(search_code)

        place_data = []
        for nearby_place in nearby_places:
            try:
                lat, lng = map(float, nearby_place.place.location.split(","))
                place_data.append(
                    {
                        "location": {
                            "lat": lat,
                            "lng": lng,
                        },
                        "name": nearby_place.place.name,
                        "place_id": nearby_place.place.place_id,
                        "rating": nearby_place.place.rating,
                    }
                )
            except ValueError:
                print(
                    f"Invalid location format: {nearby_place.place.location} for place {nearby_place.place.name}"
                )
                continue

        map_center = NearbyPlaceRepository.get_default_location()
        center_lat, center_lng = map(float, map_center.place.location.split(","))
        map_data = {
            "center": {
                "lat": center_lat,
                "lng": center_lng,
            },
            "places": place_data,
        }

        context["map_data"] = json.dumps(map_data, ensure_ascii=False)
        context["google_maps_api_key"] = os.getenv("GOOGLE_MAPS_API_KEY")
        return context

    @staticmethod
    def post(request, search_code: int):
        if search_code == NearbyPlaceRepository.CATEGORY_SEARCH:
            map_center = NearbyPlaceRepository.get_default_location()
            center_lat, center_lng = map(float, map_center.place.location.split(","))
            search_types = ["restaurant"]
            service = GoogleMapsService(os.getenv("GOOGLE_MAPS_API_KEY"))
            places = service.nearby_search(
                center=GoogleMapCoords(center_lat, center_lng),
                search_types=search_types,
                radius=1500,
                fields=[
                    "places.id",
                    "places.location",
                    "places.displayName.text",
                    "places.rating",
                ],
            )
            NearbyPlaceRepository.handle_search_code(
                category=NearbyPlaceRepository.CATEGORY_SEARCH,
                search_types=",".join(search_types),
                places=places,
            )
        return redirect(
            reverse_lazy("mrk:nearby_search", kwargs={"search_code": search_code})
        )


class CoordinateRegisterView(TemplateView):
    template_name = "gmarker/coords/create.html"

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

            # GoogleMapCoordsクラスで処理
            coords = GoogleMapCoords(latitude, longitude)

            # リポジトリを利用してアップサート処理
            nearby_place = NearbyPlaceRepository.upsert_default_location(coords)
            if nearby_place:
                print(f"upsert NearbyPlace: {nearby_place.place.location}")

            # 正常終了後、リダイレクト
            return redirect(reverse("mrk:index"))

        # フォームエラー時、再表示
        return render(request, self.template_name, {"form": form})
