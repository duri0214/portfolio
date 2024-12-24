import json
import os
import urllib.parse
import urllib.request

from django.http.response import JsonResponse
from django.shortcuts import render, redirect

from .models import StoreInformation, SignageMenuName


def index(request, search_code="9"):
    """search_code9は自拠点"""

    print("search_code: ", search_code)
    if request.method == "POST":
        temp = []
        if search_code[:1] == "1":
            # delete if record exists
            query = StoreInformation.objects.filter(category=1)
            if query.count() > 0:
                query.delete()
            # api search
            search_word = SignageMenuName.objects.get(menu_code=search_code).menu_name
            print("search at:", search_word)
            centerlatlng = StoreInformation.objects.get(category=9).shop_latlng
            types = "restaurant"
            radius = 1500
            shops = near_by_search(
                os.getenv("GOOGLE_MAPS_API_KEY"),
                search_word,
                centerlatlng,
                types,
                radius,
            )
            # insert as category 1
            if shops:
                for shop in shops:
                    # print(shop["place_id"])
                    store = StoreInformation()
                    store.category = 1
                    store.searchword = search_word
                    store.place_id = shop["place_id"]
                    store.shop_name = shop["name"]
                    store.shop_latlng = ",".join(
                        map(str, shop["geometry"]["location"].values())
                    )
                    temp.append(store)
                StoreInformation.objects.bulk_create(temp)
        elif search_code[:1] == "2":
            # delete if record exists
            query = StoreInformation.objects.filter(category=2)
            if query.count() > 0:
                query.delete()
            # insert as category 2
            shops = json.loads(request.body).get("shops")
            if shops:
                for shop in shops:
                    # print(shop["place_id"])
                    store = StoreInformation()
                    store.category = 2
                    store.searchword = "selected by you."
                    store.place_id = shop["place_id"]
                    store.shop_name = shop["shop_name"]
                    store.shop_latlng = ",".join(
                        map(str, shop["geometry"]["location"].values())
                    )
                    temp.append(store)
                StoreInformation.objects.bulk_create(temp)
            # response json
            return JsonResponse({"status": "OK"})

        # redirect 1 or 3
        return redirect("/gmarker/result/" + search_code[:1])

    else:
        # select category
        temp = StoreInformation.objects.filter(category=search_code)
        shops = []
        for i, row in enumerate(temp):
            shops.append(
                {
                    "geometry": {
                        "location": {
                            "lat": row.shop_latlng.split(",")[0],
                            "lng": row.shop_latlng.split(",")[1],
                        }
                    },
                    "radius": 1500,
                    "shop_name": row.shop_name,
                    "place_id": row.place_id,
                }
            )

        # packing
        mypos = StoreInformation.objects.get(category=9).shop_latlng
        unit = {
            "center": {"lat": mypos.split(",")[0], "lng": mypos.split(",")[1]},
            "shops": shops,
        }

        context = {
            "unit": json.dumps(unit, ensure_ascii=False),
            "google_maps_api_key": os.getenv("GOOGLE_MAPS_API_KEY"),
        }

        # render
        return render(request, "gmarker/index.html", context)


def search_detail(request, place_id):
    """ajaxから利用されます"""
    return JsonResponse(
        {"detail": get_details(os.environ.get("GOOGLE_MAPS_API_KEY"), place_id)}
    )


def get_details(api_key, place_id):
    """
    dependency
    ----------
    Places API
    parameters
    ----------
    place_id: ChIJN1t_tDeuEmsRUsoyG83frY4
    return
    ------
    e.g. https://maps.google.com/?cid=10281119596374313554

    Args:
        api_key:
    """
    ret_value = "#"
    if place_id:
        fields = (
            "address_component,adr_address,formatted_address,geometry,icon,name,"
            "permanently_closed,photo,place_id,plus_code,type,url,utc_offset,vicinity,"
            "formatted_phone_number,international_phone_number,opening_hours,"
            "website,price_level,rating,review,user_ratings_total"
        )
        url = (
            "https://maps.googleapis.com/maps/api/place/details/json?"
            "place_id={}&fields={}&key={}".format(place_id, fields, api_key)
        )
        # print('url:', url)
        res = urllib.request.urlopen(url)
        if res.code == 200:
            res_json = json.loads(res.read())
            ret_value = res_json["result"]
    return ret_value
