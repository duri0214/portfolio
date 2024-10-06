import base64
import hashlib
import hmac
import os
import secrets
from io import BytesIO

import requests
from PIL import Image
from django.http import HttpRequest
from linebot.api import LineBotApi
from linebot.models import TextSendMessage

from config.settings import MEDIA_ROOT
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
    def _get_picture(url: str) -> Image:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))

    @staticmethod
    def _resize_picture(picture: Image) -> Image:
        return picture.resize((128, 128))

    @staticmethod
    def _save_picture(picture: Image) -> str:
        random_filename = secrets.token_hex(10) + ".png"
        picture_path = MEDIA_ROOT / "linebot_engine/images" / random_filename
        picture_path.parent.mkdir(parents=True, exist_ok=True)
        picture.save(picture_path)
        return picture_path

    def picture_save(self, picture_url: str) -> str:
        picture = self._get_picture(picture_url)
        resized_picture = self._resize_picture(picture)
        picture_path = self._save_picture(resized_picture)
        return picture_path

    def handle_event(self, event, line_user_id):
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
            picture_path = self.picture_save(profile.picture_url)
            UserProfile.objects.create(
                line_user_id=line_user_id,
                display_name=profile.display_name,
                picture=picture_path,
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
                resized_picture_path = self.picture_save(picture_path)

                Message.objects.create(
                    user_profile=UserProfile.objects.get(line_user_id=line_user_id),
                    source_type=event.event_data.type,
                    picture=resized_picture_path,
                )

        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="Unsupported event type")
            )
