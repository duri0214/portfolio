import requests

from lib.geo.valueobject.coord import GoogleMapsCoord


class GooglePlacesAggregateClient:
    """Places Aggregate API の件数集計だけを呼び出すHTTPクライアント。"""

    TIMEOUT_SECONDS = 10

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://areainsights.googleapis.com/v1:computeInsights"
        self.last_error_status_code: int | None = None
        self.last_error_message = ""

    def count_places(
        self,
        center: GoogleMapsCoord,
        radius: int,
        included_types: list[str],
    ) -> int | None:
        """
        指定円内にある対象 Place Type の施設数を取得する。

        Args:
            center: 集計円の中心座標。
            radius: 集計円の半径メートル。
            included_types: 集計対象の Place Type。

        Returns:
            取得できた施設件数。HTTPエラーやパース失敗時は None。
        """
        if not included_types:
            raise ValueError("included_typesパラメータは必須です")

        try:
            response = requests.post(
                url=self.base_url,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                },
                json={
                    "insights": ["INSIGHT_COUNT"],
                    "filter": {
                        "locationFilter": {
                            "circle": {
                                "latLng": {
                                    "latitude": center.latitude,
                                    "longitude": center.longitude,
                                },
                                "radius": radius,
                            }
                        },
                        "typeFilter": {"includedTypes": included_types},
                        "operatingStatus": ["OPERATING_STATUS_OPERATIONAL"],
                    },
                },
                timeout=self.TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            self.last_error_status_code = None
            self.last_error_message = ""
            return int(response.json().get("count", 0))
        except requests.HTTPError as e:
            response = e.response
            self.last_error_status_code = (
                response.status_code if response is not None else None
            )
            self.last_error_message = self._error_message_from_response(response)
            print(f"Google Places Aggregate API HTTP error: {e}")
            return None
        except (TypeError, ValueError, requests.RequestException) as e:
            self.last_error_status_code = None
            self.last_error_message = str(e)
            print(f"Google Places Aggregate API fetch error: {e}")
            return None

    @staticmethod
    def _error_message_from_response(response) -> str:
        if response is None:
            return ""
        try:
            error_data = response.json().get("error", {})
        except ValueError:
            return response.text[:500]
        status = error_data.get("status") or ""
        message = error_data.get("message") or ""
        if status and message:
            return f"{status}: {message}"
        return message or status
