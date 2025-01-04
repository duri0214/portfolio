import json
import os

from django.http.response import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View, TemplateView

from gmarker.domain.repository.googlemaps import NearbyPlaceRepository
from gmarker.domain.service.googlemaps import GoogleMapsService
from lib.geo.valueobject.coords import GoogleMapCoords


class IndexView(TemplateView):
    template_name = "gmarker/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_code = self.kwargs.get("search_code", 9)
        print(f"{search_code=}")
        places = NearbyPlaceRepository.get_places_by_category(search_code)

        # map_data を直接作成
        map_center = NearbyPlaceRepository.get_default_location()

        center_lat, center_lng = map(float, map_center.location.split(","))
        place_data = []
        for place in places:
            try:
                lat, lng = map(float, place.location.split(","))
                place_data.append(
                    {
                        "location": {
                            "lat": lat,
                            "lng": lng,
                        },
                        "name": place.name,
                        "place_id": place.place_id,
                    }
                )
            except ValueError:
                print(
                    f"Invalid location format: {place.location} for place {place.name}"
                )
                continue
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
        print(f"{search_code=}")
        if search_code == NearbyPlaceRepository.CATEGORY_SEARCH:
            # カテゴリーサーチモード
            map_center = NearbyPlaceRepository.get_default_location()
            latitude, longitude = map(float, map_center.location.split(","))
            search_types = ["restaurant"]
            service = GoogleMapsService(os.getenv("GOOGLE_MAPS_API_KEY"))
            places = service.nearby_search(
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
                places=places,
            )
        return redirect(
            reverse_lazy("mrk:nearby_search", kwargs={"search_code": search_code})
        )


class SearchDetailView(View):
    @staticmethod
    def get(request, place_id: str):
        # TODO: PinをホバーするたびにAPIアクセスしていると思うので
        #  placeマスタを作って、マスタにあったらAPIアクセスせずに表示したい
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
