import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

import requests
from django.core.files import File
from django.http import HttpRequest
from linebot.api import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage

from config.settings import MEDIA_ROOT, SITE_URL, MEDIA_URL
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
    def _get_and_save_picture(url: str) -> str:
        response = requests.get(url)
        response.raise_for_status()
        image_data = response.content
        random_filename = secrets.token_hex(10) + ".png"
        picture_path = MEDIA_ROOT / "linebot_engine/images" / random_filename
        picture_path.parent.mkdir(parents=True, exist_ok=True)
        with open(picture_path, "wb") as fd:
            fd.write(image_data)
        return str(picture_path)

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

        # Botをフォローした時
        if event.is_follow():
            profile = line_bot_api.get_profile(event.source.user_id)
            picture_path = self._get_and_save_picture(profile.picture_url)
            with open(picture_path, "rb") as f:
                Message.objects.create(
                    user_profile=UserProfile.objects.get(line_user_id=line_user_id),
                    source_type=event.event_data.type,
                    picture=File(f),
                )

        # Botがブロックされたとき
        elif event.is_unfollow():
            UserProfile.objects.filter(line_user_id=line_user_id).delete()

        # メッセージが発生したとき
        elif event.is_message():
            if event.event_data.type == "text":
                Message.objects.create(
                    user_profile=UserProfile.objects.get(line_user_id=line_user_id),
                    source_type=event.event_data.type,
                    message=event.event_data.text,
                )

            elif event.event_data.type == "image":
                message_content = line_bot_api.get_message_content(event.event_data.id)

                random_filename = secrets.token_hex(10) + ".png"
                picture_path = MEDIA_ROOT / "linebot_engine/images" / random_filename
                picture_path.parent.mkdir(parents=True, exist_ok=True)

                with open(picture_path, "wb") as fd:
                    for chunk in message_content.iter_content():
                        fd.write(chunk)

                with open(picture_path, "rb") as f:
                    Message.objects.create(
                        user_profile=UserProfile.objects.get(line_user_id=line_user_id),
                        source_type=event.event_data.type,
                        picture=File(f),
                    )

                full_picture_url = str(
                    Path(SITE_URL)
                    / MEDIA_URL
                    / "linebot_engine/images"
                    / random_filename
                )

                image_send_message = ImageSendMessage(
                    original_content_url=full_picture_url,
                    preview_image_url=full_picture_url,
                )
                text_message = TextSendMessage(text="処理が完了しました")
                line_bot_api.reply_message(
                    event.reply_token, [image_send_message, text_message]
                )

        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="Unsupported event type")
            )
