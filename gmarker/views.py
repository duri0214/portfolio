import json
import os

from django.http.response import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View, TemplateView

from gmarker.domain.repository.googlemaps import NearbyPlaceRepository
from gmarker.domain.service.googlemaps import GoogleMapsService
from gmarker.domain.valueobject.googlemaps import PlaceVO
from lib.geo.valueobject.coords import GoogleMapCoords


class IndexView(TemplateView):
    template_name = "gmarker/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_code = self.kwargs.get("search_code", 9)
        print(f"{search_code=}")
        places = NearbyPlaceRepository.get_places_by_category(search_code)
        shops = []
        for place in places:
            shops.append(
                {
                    "geometry": {
                        "location": {
                            "lat": place.location.split(",")[0],
                            "lng": place.location.split(",")[1],
                        }
                    },
                    "radius": 1500,
                    "shop_name": place.name,
                    "place_id": place.place_id,
                }
            )
        map_center = NearbyPlaceRepository.get_default_location()
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
    def post(request, search_code: int):
        print(f"{search_code=}")
        if search_code == NearbyPlaceRepository.CATEGORY_SEARCH:
            # カテゴリーサーチモード
            map_center = NearbyPlaceRepository.get_default_location()
            latitude, longitude = map(float, map_center.location.split(","))
            search_types = ["restaurant"]
            service = GoogleMapsService(os.getenv("GOOGLE_MAPS_API_KEY"))
            # TODO: shopじゃなくてplaceだよね
            shops = service.nearby_search(
                center=GoogleMapCoords(latitude, longitude),
                search_types=search_types,
                radius=1500,
                fields=[
                    "places.id",
                    "places.location",
                    "places.displayName.text",
                    "places.photos",
                ],
            )
            NearbyPlaceRepository.handle_search_code(
                category=NearbyPlaceRepository.CATEGORY_SEARCH,
                search_types=",".join(search_types),
                places=shops,
            )
        elif search_code == NearbyPlaceRepository.PIN_SELECT:
            # ピン選択モード
            selected_place_list = []
            for place in json.loads(request.body).get("places"):
                geometry_data = place["geometry"]
                location_data = geometry_data["location"]
                selected_place_list.append(
                    PlaceVO(
                        place_id=place["place_id"],
                        location=GoogleMapCoords(
                            latitude=location_data["lat"],
                            longitude=location_data["lng"],
                        ),
                        name=place["shop_name"],
                        photos=[],
                        rating=0,  # TODO: jsのajax経由でもらってください
                        reviews=[],
                    )
                )

            print(f"{selected_place_list=}")
            NearbyPlaceRepository.handle_search_code(
                category=NearbyPlaceRepository.PIN_SELECT,
                search_types="PIN_SELECT",
                places=selected_place_list,
            )
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
            fields=[
                "places.id",
                "places.location",
                "places.displayName.text",
                "places.photos",
                "places.rating",
                "places.reviews",
            ],
        )

        return JsonResponse({"detail": store_details})
