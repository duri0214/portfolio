import json
import os

from django.http.response import JsonResponse
from django.shortcuts import render, redirect
from django.views.generic import View

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

def index(request, search_code="9"):
    """search_code9は自拠点"""

    print("search_code: ", search_code)
    if request.method == "POST":
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
            )
            handle_search_code(NearbyPlace.CATEGORY_SEARCH, search_word, shops)
        elif search_code[:1] == "2":
            # ピン選択モード
            shops = json.loads(request.body).get("shops")
            handle_search_code(NearbyPlace.PIN_SELECT, "selected by you.", shops)
            return JsonResponse({"status": "OK"})

        # redirect 1 or 3
        return redirect("/gmarker/result/" + search_code[:1])

    else:
        # select category
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

        # packing
        map_center = NearbyPlace.objects.get(category=NearbyPlace.DEFAULT_LOCATION)
        unit = {
            "center": {
                "lat": map_center.location.split(",")[0],
                "lng": map_center.location.split(",")[1],
            },
            "shops": shops,
        }

        context = {
            "unit": json.dumps(unit, ensure_ascii=False),
            "google_maps_api_key": os.getenv("GOOGLE_MAPS_API_KEY"),
        }

        # render
        return render(request, "gmarker/index.html", context)


class SearchDetailView(View):
    @staticmethod
    def get(request, *args, **kwargs):
        # TODO: PinをホバーするたびにAPIアクセスしていると思うので
        #  placeマスタを作って、マスタにあったらAPIアクセスせずに表示したい
        place_id = kwargs["place_id"]
        service = GoogleMapsService(os.getenv("GOOGLE_MAPS_API_KEY"))
        store_details = service.get_place_details(place_id)

        return JsonResponse({"detail": store_details})
