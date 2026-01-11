import requests
from datetime import date
import time


class KokkaiAPIClient:
    BASE_URL = "https://kokkai.ndl.go.jp/api/meeting"

    def search_meetings(self, start_date: date, end_date: date):
        """
        指定された期間の会議一覧を取得する。
        """
        params = {
            "from": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d"),
            "recordPacking": "json",
        }
        # 実際には件数だけ知りたい場合でも、一回の叩きで取得できる件数に限りがある可能性がある。
        # 開催日インデックス構築のためには、会議単位の情報を取得する必要がある。
        # 検索用API: https://kokkai.ndl.go.jp/api.html
        # "meeting" エンドポイントを使用

        response = requests.get(self.BASE_URL, params=params)
        response.raise_for_status()
        return response.json()

    def get_meeting_counts_by_date(self, start_date: date, end_date: date):
        """
        日付ごとの会議件数を取得する。
        APIの仕様上、一度に取得できる件数に上限(10件)があるため、ループが必要になる場合がある。
        """
        results = {}
        current_start = 1

        while True:
            params = {
                "from": start_date.strftime("%Y-%m-%d"),
                "until": end_date.strftime("%Y-%m-%d"),
                "startRecord": current_start,
                "maximumRecords": 10,
                "recordPacking": "json",
            }

            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if "meetingRecord" not in data:
                break

            for record in data["meetingRecord"]:
                d = record["date"]
                results[d] = results.get(d, 0) + 1

            next_start = data.get("nextRecordPosition")
            if not next_start or next_start > data.get("numberOfRecords", 0):
                break
            current_start = next_start
            time.sleep(1)  # API負荷軽減

        return results
