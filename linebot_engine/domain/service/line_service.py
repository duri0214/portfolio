import base64
import hashlib
import hmac
import os
import secrets
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image
from django.http import HttpRequest

from config.settings import MEDIA_ROOT


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
        folder_path = Path(MEDIA_ROOT) / "images"
        folder_path.mkdir(parents=True, exist_ok=True)
        random_filename = secrets.token_hex(5) + ".png"
        picture_path = str(folder_path / random_filename)
        picture.save(picture_path)
        return picture_path

    def picture_save(self, picture_url: str) -> str:
        picture = self._get_picture(picture_url)
        resized_picture = self._resize_picture(picture)
        picture_path = self._save_picture(resized_picture)
        return picture_path
