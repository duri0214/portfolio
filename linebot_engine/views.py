import json
import os

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from linebot import LineBotApi
from linebot.models import Message

from linebot_engine.domain.service.line_service import LineService
from linebot_engine.domain.valueobject.line import WebhookEvent
from linebot_engine.models import UserProfile

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
        if not LineService.is_valid_signature(request):
            return HttpResponse(status=403)  # return 'Forbidden'

        request_json = json.loads(request.body.decode("utf-8"))
        events = [WebhookEvent(event) for event in request_json["events"]]

        for event in events:
            # TODO: .is_group() のときの処理はTBD
            if event.source and event.source.is_user():
                line_user_id = event.source.user_id

                if line_user_id != WEBHOOK_VERIFICATION_USER_ID:
                    # botをフォローしたとき
                    line_bot_api = LineBotApi(
                        os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
                    )
                    profile = line_bot_api.get_profile(event.source.user_id)
                    picture = LineService.get_picture(profile.picture_url)
                    resized_picture = LineService.picture_resize(picture)
                    picture_path = LineService.picture_save(resized_picture)
                    if event.is_follow():
                        UserProfile.objects.create(
                            user_id=line_user_id,
                            display_name=profile.display_name,
                            picture=picture_path,
                        )
                    # botがブロックされたとき
                    if event.is_unfollow():
                        UserProfile.objects.filter(line_user_id).delete()

                    # replyが発生したとき
                    if event.is_message():
                        Message.objects.create(
                            user_profile=UserProfile.objects.get(user_id=line_user_id),
                            source_type=event.event_data.type,
                            message=event.event_data.text,
                        )

        return HttpResponse(status=200)
