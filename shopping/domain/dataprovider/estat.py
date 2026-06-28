import requests


class EstatCsvClient:
    """出店計画で使う e-Stat CSV を取得するHTTPクライアント。"""

    TIMEOUT_SECONDS = 20

    def get_text(self, url: str, encoding: str | None = None) -> str:
        response = requests.get(url, timeout=self.TIMEOUT_SECONDS)
        response.raise_for_status()
        response.encoding = encoding or response.apparent_encoding
        return response.text
