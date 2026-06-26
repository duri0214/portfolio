import requests


class EstatApiClient:
    """
    e-Stat API v3.0 JSON エンドポイントを呼び出すクライアントです。
    """

    BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"
    TIMEOUT_SECONDS = 20

    def __init__(self, app_id: str):
        self.app_id = app_id

    def get_stats_list(self, search_word: str) -> dict:
        """
        統計表一覧を検索します。

        Args:
            search_word: 検索語。

        Returns:
            dict: e-Stat API レスポンス。
        """
        return self._get(
            "getStatsList",
            {
                "searchWord": search_word,
            },
        )

    def get_meta_info(self, stats_data_id: str) -> dict:
        """
        統計表のメタ情報を取得します。

        Args:
            stats_data_id: e-Stat 統計表表示ID。

        Returns:
            dict: e-Stat API レスポンス。
        """
        return self._get("getMetaInfo", {"statsDataId": stats_data_id})

    def get_stats_data(self, stats_data_id: str, area_code: str, filters: dict) -> dict:
        """
        指定地域・指定統計表の統計値を取得します。

        Args:
            stats_data_id: e-Stat 統計表表示ID。
            area_code: e-Stat 地域コード。
            filters: e-Stat API に渡す絞り込み条件。

        Returns:
            dict: e-Stat API レスポンス。
        """
        params = {
            "statsDataId": stats_data_id,
            "cdArea": area_code,
            "metaGetFlg": "Y",
            "cntGetFlg": "N",
            **filters,
        }
        return self._get("getStatsData", params)

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
