"""views.py"""

import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import LinePush


@csrf_exempt
def callback(request):
    """ラインの友達追加時に呼び出され、ラインのIDを登録する"""
    if request.method == "POST":
        request_json = json.loads(request.body.decode("utf-8"))
        events = request_json["events"]
        line_user_id = None
        try:
            line_user_id = events[0]["source"]["userId"]
        except IndexError:
            raise IndexError(f"events: {events}")

        # webhook connection check at fixed id 'Udea...beef'
        if line_user_id != "Udeadbeefdeadbeefdeadbeefdeadbeef":
            # follow || unblock
            if events[0]["type"] == "follow":
                LinePush.objects.create(line_user_id)
            # block
            if events[0]["type"] == "unfollow":
                LinePush.objects.filter(line_user_id).delete()

    return HttpResponse("ok", status=200)
