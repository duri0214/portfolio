"""views.py"""
import urllib.request
import json
from django.shortcuts import render, redirect
from django.http.response import JsonResponse

from django.conf import settings
from .models import StoreInformation, SignageMenuName

# read APIKEY
with open(settings.BASE_DIR.joinpath('gmarker/api_setting/apikey.txt'), mode='r') as file:
    APIKEY = file.read()

def index(request, searchcode='9'):
    """searchcode9は自拠点"""

    print("searchcode: ", searchcode)
    if request.method == 'POST':
        temp = []
        if searchcode[:1] == '1':
            # delete if record exists
            query = StoreInformation.objects.filter(category=1)
            if query.count() > 0:
                query.delete()
            # api search
            searchword = SignageMenuName.objects.get(menu_code=searchcode).menu_name
            print('search at:', searchword)
            centerlatlng = StoreInformation.objects.get(category=9).shop_latlng
            types = 'restaurant'
            radius = 1500
            shops = nearbysearch(APIKEY, searchword, centerlatlng, types, radius)
            # insert as category 1
            if shops:
                for shop in shops:
                    # print(shop["place_id"])
                    store = StoreInformation()
                    store.category = 1
                    store.searchword = searchword
                    store.place_id = shop["place_id"]
                    store.shop_name = shop["name"]
                    store.shop_latlng = ','.join(map(str, shop["geometry"]["location"].values()))
                    temp.append(store)
                StoreInformation.objects.bulk_create(temp)
        elif searchcode[:1] == '2':
            # delete if record exists
            query = StoreInformation.objects.filter(category=2)
            if query.count() > 0:
                query.delete()
            # insert as category 2
            shops = json.loads(request.body).get('shops')
            if shops:
                for shop in shops:
                    # print(shop["place_id"])
                    store = StoreInformation()
                    store.category = 2
                    store.searchword = "selected by you."
                    store.place_id = shop["place_id"]
                    store.shop_name = shop["shop_name"]
                    store.shop_latlng = ','.join(map(str, shop["geometry"]["location"].values()))
                    temp.append(store)
                StoreInformation.objects.bulk_create(temp)
            # responce json
            return JsonResponse({"status" : "OK"})

        # redirect 1 or 3
        return redirect('/gmarker/result/' + searchcode[:1])

    else:
        # select category
        temp = StoreInformation.objects.filter(category=searchcode)
        shops = []
        for i, row in enumerate(temp):
            shops.append({
                "geometry": {
                    "location": {
                        "lat": row.shop_latlng.split(',')[0],
                        "lng": row.shop_latlng.split(',')[1]
                    }
                },
                "radius": 1500,
                "shop_name": row.shop_name,
                "place_id": row.place_id
            })

        # packing
        mypos = StoreInformation.objects.get(category=9).shop_latlng
        unit = {"center": {"lat": mypos.split(',')[0], "lng": mypos.split(',')[1]}, "shops": shops}

        context = {
            'unit': json.dumps(unit, ensure_ascii=False),
        }

        # render
        return render(request, 'gmarker/index.html', context)

def searchdetail(request, place_id):
    '''ajaxから利用されます'''
    return JsonResponse({"detail" : get_details(APIKEY, place_id)})

def nearbysearch(apikey, place, centerlatlng, types, radius):
    '''
    dependency
    ----------
    Places API

    parameters
    ----------
    place: 東京都

    return
    --------
    a place\n
    place_id, rating\n
    e.g. CmRaAAAARRAYThPn0sTB1aE-Afx0_..., 4
    '''
    url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?' \
        'location={}&radius={}&type={}&keyword={}&' \
        'key={}'
    url = url.format(centerlatlng, radius, types, urllib.parse.quote(place), apikey)
    # print("nearbysearch:", url)
    res = urllib.request.urlopen(url)
    retvalue = None
    if res.code == 200:
        res_json = json.loads(res.read())
        if res_json.get("results"):
            retvalue = res_json["results"]
    return retvalue

def get_details(apikey, place_id):
    '''
    dependency
    ----------
    Places API
    parameters
    ----------
    place_id: ChIJN1t_tDeuEmsRUsoyG83frY4
    return
    ------
    e.g. https://maps.google.com/?cid=10281119596374313554
    '''
    retvalue = '#'
    if place_id:
        fields = 'address_component,adr_address,formatted_address,geometry,icon,name,' \
            'permanently_closed,photo,place_id,plus_code,type,url,utc_offset,vicinity,' \
            'formatted_phone_number,international_phone_number,opening_hours,' \
            'website,price_level,rating,review,user_ratings_total'
        url = 'https://maps.googleapis.com/maps/api/place/details/json?' \
            'place_id={}&fields={}&key={}'.format(place_id, fields, apikey)
        # print('url:', url)
        res = urllib.request.urlopen(url)
        if res.code == 200:
            res_json = json.loads(res.read())
            retvalue = res_json["result"]
    return retvalue
