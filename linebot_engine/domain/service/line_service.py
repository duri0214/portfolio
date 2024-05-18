import base64
import hashlib
import hmac
import os

from django.http import HttpRequest


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
