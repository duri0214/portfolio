import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

import requests
from django.core.files.base import ContentFile
from django.http import HttpRequest
from linebot.api import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage

from config.settings import SITE_URL, MEDIA_URL
from linebot_engine.domain.valueobject.line import WebhookEvent
from linebot_engine.models import UserProfile, Message


class LineService:
    """A service class to encapsulate LINE related business logic."""

    @staticmethod
    def is_valid_signature(request: HttpRequest) -> bool:
        """Check LINE webhook request signature."""
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

    @staticmethod
    def _get_picture_content(url: str) -> ContentFile:
        response = requests.get(url)
        response.raise_for_status()
        return ContentFile(response.content)

    def handle_event(self, event: WebhookEvent, line_user_id: str):
        """
        follow, unfollow and message という種類の異なるイベントを処理します

        is_follow(): プロフィール画像を保存し、ユーザープロフィールを作成します
        is_unfollow(): ユーザープロフィールを削除します
        is_message():
            text: メッセージの記録を作成します
            image: 画像のコンテンツを取得し、`self.picture_save()` で保存します

        Args:
            event: イベントの情報を含むLineのイベントオブジェクト
            line_user_id: イベントに関連付けられたLineのユーザーID
        """
        line_bot_api = LineBotApi(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"))

        if event.is_follow():
            profile = line_bot_api.get_profile(event.source.user_id)
            picture_file = self._get_picture_content(profile.picture_url)
            picture_file.name = f"{secrets.token_hex(10)}.png"
            UserProfile.objects.create(
                line_user_id=line_user_id,
                display_name=profile.display_name,
                picture=picture_file,
            )

        elif event.is_unfollow():
            UserProfile.objects.filter(line_user_id=line_user_id).delete()

        elif event.is_message():
            if event.event_data.type == "text":
                Message.objects.create(
                    user_profile=UserProfile.objects.get(line_user_id=line_user_id),
                    source_type=event.event_data.type,
                    message=event.event_data.text,
                )
                text_message = TextSendMessage(text="textが記録されました")
                line_bot_api.reply_message(event.reply_token, text_message)

            elif event.event_data.type == "image":
                message_content = line_bot_api.get_message_content(event.event_data.id)
                picture_file = self._get_and_save_picture(message_content.content)
                picture_file.name = f"{secrets.token_hex(10)}.png"

                Message.objects.create(
                    user_profile=UserProfile.objects.get(line_user_id=line_user_id),
                    source_type=event.event_data.type,
                    picture=picture_file,
                )

                full_picture_url = str(
                    Path(SITE_URL)
                    / MEDIA_URL
                    / "linebot_engine/images"
                    / picture_file.name
                )

                image_send_message = ImageSendMessage(
                    original_content_url=full_picture_url,
                    preview_image_url=full_picture_url,
                )
                text_message = TextSendMessage(
                    text="imageが記録されました。ほらこれでしょ？"
                )
                line_bot_api.reply_message(
                    event.reply_token, [image_send_message, text_message]
                )

        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="Unsupported event type")
            )
