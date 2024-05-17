import json

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import LinePush

WEBHOOK_VERIFICATION_USER_ID = "Udeadbeefdeadbeefdeadbeefdeadbeef"


@method_decorator(csrf_exempt, name="dispatch")
class CallbackView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        """
        ラインの友達追加時に呼び出され、ラインのIDを登録する

        Notes: LINE DEVELOPERSの画面からWebhookの接続をテストした場合
               実際のイベント（ユーザーのアクションなど）がないため、eventsデータは存在せず、空の配列が返される
        """
        request_json = json.loads(request.body.decode("utf-8"))
        events = request_json["events"]

        if events:
            line_user_id = events[0]["source"]["userId"]

            if line_user_id != WEBHOOK_VERIFICATION_USER_ID:
                # botをフォローしたとき
                if events[0]["type"] == "follow":
                    LinePush.objects.create(line_user_id)
                # botがブロックされた
                if events[0]["type"] == "unfollow":
                    LinePush.objects.filter(line_user_id).delete()

        return HttpResponse(status=200)
