import base64
import hashlib
import hmac
import json
import os

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import LinePush

WEBHOOK_VERIFICATION_USER_ID = "Udeadbeefdeadbeefdeadbeefdeadbeef"


@method_decorator(csrf_exempt, name="dispatch")
class CallbackView(View):
    @staticmethod
    def is_valid_signature(request):
        body = request.body.decode("utf-8")
        _hash = hmac.new(
            os.environ.get("LINE_CHANNEL_SECRET").encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(_hash).decode("utf-8")

        # Retrieve X-Line-Signature header value
        x_line_signature = request.META.get("HTTP_X_LINE_SIGNATURE")

        # Compare X-Line-Signature header value and the signature calculated in the code
        return x_line_signature == signature

    def post(self, request, *args, **kwargs):
        """
        ラインの友達追加時に呼び出され、ラインのIDを登録する

        Notes: LINE DEVELOPERSの画面からWebhookの接続をテストした場合
               実際のイベント（ユーザーのアクションなど）がないため、eventsデータは存在せず、空の配列が返される
        """
        if not self.is_valid_signature(request):
            return HttpResponse(status=403)  # return 'Forbidden'

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
