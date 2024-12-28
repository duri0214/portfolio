import json
import os

from django.http.response import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View, TemplateView

from gmarker.domain.repository.googlemaps import NearbyPlaceRepository
from gmarker.domain.service.googlemaps import GoogleMapsService
from gmarker.domain.valueobject.googlemaps import PlaceVO
from gmarker.models import NearbyPlace
from lib.geo.valueobject.coords import GoogleMapCoords


def handle_search_code(category: int, search_types: str, places: list[PlaceVO]):
    NearbyPlaceRepository.delete_by_category(category)
    if places:
        new_places = []
        for place in places:
            # TODO: modelである必要はあるか？repositoryに移管できるか？
            store = NearbyPlace(
                category=category,
                search_types=search_types,
                place_id=place.place_id,
                name=place.name,
                location=place.location.to_str(),
            )
            new_places.append(store)
        NearbyPlaceRepository.bulk_create(new_places)


class IndexView(TemplateView):
    template_name = "gmarker/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_code = self.kwargs.get("search_code", "9")
        print(f"{search_code=}")
        temp = NearbyPlace.objects.filter(category=search_code)  # TODO: repositoryへ
        shops = []
        for i, row in enumerate(temp):
            shops.append(
                {
                    "geometry": {
                        "location": {
                            "lat": row.location.split(",")[0],
                            "lng": row.location.split(",")[1],
                        }
                    },
                    "radius": 1500,
                    "shop_name": row.name,
                    "place_id": row.place_id,
                }
            )
        map_center = NearbyPlace.objects.get(
            category=NearbyPlace.DEFAULT_LOCATION
        )  # TODO: repositoryへ
        # TODO: この値構成、整理できないか？
        unit = {
            "center": {
                "lat": map_center.location.split(",")[0],
                "lng": map_center.location.split(",")[1],
            },
            "shops": shops,
        }
        context["unit"] = json.dumps(unit, ensure_ascii=False)
        context["google_maps_api_key"] = os.getenv("GOOGLE_MAPS_API_KEY")
        return context

    @staticmethod
    def post(request, search_code: str):
        print(f"{search_code=}")
        if search_code == "1":
            # カテゴリーサーチモード
            map_center = NearbyPlace.objects.get(
                category=NearbyPlace.DEFAULT_LOCATION
            )  # TODO: repositoryへ（repositoryが定数を持つ）
            latitude, longitude = map(float, map_center.location.split(","))
            search_types = ["restaurant"]
            service = GoogleMapsService(os.getenv("GOOGLE_MAPS_API_KEY"))
            fields = [
                "places.id",
                "places.location",
                "places.displayName.text",
                "places.formattedAddress",
                "places.photos",
            ]
            # TODO: shopじゃなくてplaceだよね
            shops = service.nearby_search(
                center=GoogleMapCoords(latitude, longitude),
                search_types=search_types,
                radius=1500,
                fields=fields,
            )
            # TODO: repositoryへ（repositoryが定数を持つ）
            handle_search_code(
                NearbyPlace.CATEGORY_SEARCH, ",".join(search_types), shops
            )
        elif search_code == "2":
            # ピン選択モード
            shops = json.loads(request.body).get("shops")
            handle_search_code(
                NearbyPlace.PIN_SELECT, "PIN_SELECT", shops
            )  # TODO: repositoryへ（repositoryが定数を持つ）
            return JsonResponse({"status": "OK"})
        return redirect(
            reverse_lazy("mrk:nearby_search", kwargs={"search_code": search_code})
        )


class SearchDetailView(View):
    @staticmethod
    def get(request, *args, **kwargs):
        # TODO: PinをホバーするたびにAPIアクセスしていると思うので
        #  placeマスタを作って、マスタにあったらAPIアクセスせずに表示したい
        place_id = kwargs["place_id"]
        service = GoogleMapsService(os.getenv("GOOGLE_MAPS_API_KEY"))
        store_details = service.get_place_details(
            place_id,
            fields=["name", "formatted_address", "rating"],
        )

        return JsonResponse({"detail": store_details})
