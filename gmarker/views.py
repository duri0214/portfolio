import json
import os

from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from gmarker.domain.repository.googlemaps import NearbyPlaceRepository
from gmarker.domain.service.googlemaps import GoogleMapsService
from lib.geo.valueobject.coords import GoogleMapCoords


class IndexView(TemplateView):
    template_name = "gmarker/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_code = self.kwargs.get("search_code", 9)
        places = NearbyPlaceRepository.get_places_by_category(search_code)

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

        map_center = NearbyPlaceRepository.get_default_location()
        center_lat, center_lng = map(float, map_center.location.split(","))
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
