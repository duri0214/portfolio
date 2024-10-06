import json

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from linebot_engine.domain.service.line_service import LineService
from linebot_engine.domain.valueobject.line import WebhookEvent

WEBHOOK_VERIFICATION_USER_ID = "Udeadbeefdeadbeefdeadbeefdeadbeef"


@method_decorator(csrf_exempt, name="dispatch")
class CallbackView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        """
        LINEからのWebhook通知を処理する

        Notes: LINE DEVELOPERS（ビジネスアカウントログイン）の画面からWebhookの接続をテストした場合、
          実際のイベント（ユーザーのアクションなど）がないため、空の配列が返される
        """
        line_service = LineService()
        if not line_service.is_valid_signature(request):
            return HttpResponse(status=403)

        request_json = json.loads(request.body.decode("utf-8"))
        events = [WebhookEvent(event) for event in request_json["events"]]

        for event in events:
            # TODO: .is_group() のときの処理はTBD
            if event.source and event.source.is_user():
                line_user_id = event.source.user_id

                if line_user_id != WEBHOOK_VERIFICATION_USER_ID:
                    line_service.handle_event(event, line_user_id)

        return HttpResponse(status=200)
