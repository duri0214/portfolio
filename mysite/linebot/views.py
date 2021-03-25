"""views.py"""
import urllib.request
import json
from django.http import HttpResponseBadRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.conf import settings
from .models import LinePush

# read accesstoken
with open(settings.BASE_DIR + '/linebot/api_setting/accesstoken.txt', mode='r') as file:
    ACCESSTOKEN = file.read()

@csrf_exempt
def callback(request):
    """ラインの友達追加時に呼び出され、ラインのIDを登録する。"""
    if request.method == 'POST':
        request_json = json.loads(request.body.decode('utf-8'))
        events = request_json['events']
        line_user_id = events[0]['source']['userId']

        # webhook connection check at fixed id 'Udea...beef'
        if line_user_id != 'Udeadbeefdeadbeefdeadbeefdeadbeef':
            # follow || unblock
            if events[0]['type'] == 'follow':
                LinePush.objects.create(line_user_id)
            # block
            if events[0]['type'] == 'unfollow':
                LinePush.objects.filter(line_user_id).delete()

    return HttpResponse()
