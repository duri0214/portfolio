import json
import os

from django.http.response import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View, TemplateView

from gmarker.domain.repository.googlemaps import NearbyPlaceRepository
from gmarker.domain.service.googlemaps import GoogleMapsService
from gmarker.domain.valueobject.googlemaps import PlaceVO
from gmarker.models import NearbyPlace, CategorySearchMaster
from lib.geo.valueobject.coords import GoogleMapCoords


def handle_search_code(category: int, search_word: str, places: list[PlaceVO]):
    NearbyPlaceRepository.delete_by_category(category)
    if places:
        new_places = []
        for place in places:
            store = NearbyPlace(
                category=category,
                search_word=search_word,
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
        temp = NearbyPlace.objects.filter(category=search_code)
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
        map_center = NearbyPlace.objects.get(category=NearbyPlace.DEFAULT_LOCATION)
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

    def post(self, request, *args, **kwargs):
        search_code = self.kwargs.get("search_code", "9")
        print(f"{search_code=}")
        if search_code[:1] == "1":
            # カテゴリーサーチモード
            search_word = CategorySearchMaster.objects.get(code=search_code).name
            print(f"{search_word=}")
            map_center = NearbyPlace.objects.get(category=NearbyPlace.DEFAULT_LOCATION)
            latitude, longitude = map(float, map_center.location.split(","))
            types = "restaurant"
            radius = 1500
            service = GoogleMapsService(os.getenv("GOOGLE_MAPS_API_KEY"))
            shops = service.nearby_search(
                search_word,
                GoogleMapCoords(latitude, longitude),
                types,
                radius,
                fields=["name", "formatted_address", "rating"],
            )
            handle_search_code(NearbyPlace.CATEGORY_SEARCH, search_word, shops)
        elif search_code[:1] == "2":
            # ピン選択モード
            shops = json.loads(request.body).get("shops")
            handle_search_code(NearbyPlace.PIN_SELECT, "selected by you.", shops)
            return JsonResponse({"status": "OK"})
        return redirect(
            reverse_lazy("mrk:nearby_search", kwargs={"search_code": search_code[:1]})
        )


class SearchDetailView(View):
    @staticmethod
    def get(request, *args, **kwargs):
        # TODO: PinをホバーするたびにAPIアクセスしていると思うので
        #  placeマスタを作って、マスタにあったらAPIアクセスせずに表示したい
        place_id = kwargs["place_id"]
        service = GoogleMapsService(os.getenv("GOOGLE_MAPS_API_KEY"))
        store_details = service.get_place_details(place_id)

        return JsonResponse({"detail": store_details})
