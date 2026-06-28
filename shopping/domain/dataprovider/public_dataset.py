import requests


class PublicDatasetClient:
    """出店計画で使う公開データソースを取得するHTTPクライアント。"""

    TIMEOUT_SECONDS = 20

    def get_json(self, url: str, params: dict | None = None) -> dict:
        response = requests.get(url, params=params, timeout=self.TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()

    def get_text(self, url: str, encoding: str | None = None) -> str:
        response = requests.get(url, timeout=self.TIMEOUT_SECONDS)
        response.raise_for_status()
        response.encoding = encoding or response.apparent_encoding
        return response.text
