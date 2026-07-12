import requests


class EstatApiClient:
    """
    e-Stat API v3.0 JSON エンドポイントを呼び出すクライアントです。
    """

    BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"
    TIMEOUT_SECONDS = 20

    def __init__(self, app_id: str):
        self.app_id = app_id

    def get_stats_data(self, stats_data_id: str) -> dict:
        """
        指定した統計表の統計値を取得します。

        Args:
            stats_data_id: e-Stat 統計表表示ID。

        Returns:
            dict: e-Stat API レスポンス。
        """
        return self._get(
            "getStatsData",
            {
                "statsDataId": stats_data_id,
                "metaGetFlg": "Y",
                "cntGetFlg": "N",
            },
        )

    def get_stats_list(self, params: dict) -> dict:
        """
        条件に合う統計表の一覧を取得します。

        Args:
            params: getStatsList に渡す検索条件。

        Returns:
            dict: e-Stat API レスポンス。
        """
        return self._get("getStatsList", params)

    def _get(self, endpoint: str, params: dict) -> dict:
        request_params = {
            "appId": self.app_id,
            "lang": "J",
            **params,
        }
        response = requests.get(
            f"{self.BASE_URL}/{endpoint}",
            params=request_params,
            timeout=self.TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
