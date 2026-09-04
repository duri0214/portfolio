from datetime import date

import requests

from ..valueobject.meeting import (
    MeetingCatalogRecord,
    MeetingCatalogPage,
    MeetingRecord,
    MeetingSearchResult,
    SpeechRecord,
)


class KokkaiAPIClient:
    MEETING_LIST_URL = "https://kokkai.ndl.go.jp/api/meeting_list"
    MEETING_URL = "https://kokkai.ndl.go.jp/api/meeting"

    def search_meeting_catalog(
        self, start_date: date, end_date: date, start_record: int = 1
    ) -> MeetingCatalogPage:
        """指定期間の会議録メタデータだけを取得する。"""
        params = {
            "from": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d"),
            "startRecord": start_record,
            "maximumRecords": 100,
            "recordPacking": "json",
        }
        data = self._request(self.MEETING_LIST_URL, params)
        meeting_catalog_records = [
            MeetingCatalogRecord(
                issue_id=record["issueID"],
                image_kind=record["imageKind"],
                search_object=record["searchObject"],
                session=record["session"],
                name_of_house=record["nameOfHouse"],
                name_of_meeting=record["nameOfMeeting"],
                issue=record["issue"],
                date=record["date"],
                closing=record.get("closing"),
                meeting_url=record["meetingURL"],
                pdf_url=record.get("pdfURL"),
            )
            for record in data.get("meetingRecord", [])
        ]
        return MeetingCatalogPage(
            records=meeting_catalog_records,
            next_record_position=data.get("nextRecordPosition"),
        )

    def search_meetings(
        self, start_date: date, end_date: date, start_record: int = 1
    ) -> MeetingSearchResult:
        """
        指定された期間の会議一覧を取得する。
        """
        params: dict[str, str | int] = {
            "from": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d"),
            "startRecord": start_record,
            "maximumRecords": 10,
            "recordPacking": "json",
        }
        return self._search_meetings(params)

    def fetch_meeting(self, meeting_id: str) -> MeetingSearchResult:
        """指定した会議録IDの全文を取得する。"""
        return self._search_meetings(
            {
                "issueID": meeting_id,
                "maximumRecords": 1,
                "recordPacking": "json",
            }
        )

    def _search_meetings(self, params: dict[str, str | int]) -> MeetingSearchResult:
        data = self._request(self.MEETING_URL, params)

        meeting_records = []
        for record in data.get("meetingRecord", []):
            speech_records = []
            for speech in record.get("speechRecord", []):
                speech_records.append(
                    SpeechRecord(
                        speech_id=speech["speechID"],
                        speaker=speech["speaker"],
                        speaker_yomi=speech.get("speakerYomi"),
                        speaker_group=speech.get("speakerGroup"),
                        speaker_position=speech.get("speakerPosition"),
                        speaker_role=speech.get("speakerRole"),
                        speech=speech.get("speech"),
                        speech_order=speech["speechOrder"],
                        start_page=speech.get("startPage"),
                        create_time=speech.get("createTime", ""),
                        update_time=speech.get("updateTime", ""),
                        speech_url=speech["speechURL"],
                    )
                )

            meeting_records.append(
                MeetingRecord(
                    issue_id=record["issueID"],
                    image_kind=record["imageKind"],
                    search_object=record["searchObject"],
                    session=record["session"],
                    name_of_house=record["nameOfHouse"],
                    name_of_meeting=record["nameOfMeeting"],
                    issue=record["issue"],
                    date=record["date"],
                    closing=record.get("closing"),
                    speech_records=speech_records,
                    meeting_url=record["meetingURL"],
                    pdf_url=record.get("pdfURL"),
                )
            )

        return MeetingSearchResult(
            number_of_records=data.get("numberOfRecords", 0),
            number_of_return_records=data.get("numberOfReturn", 0),
            start_record=data.get("startRecord", 1),
            next_record_position=data.get("nextRecordPosition"),
            meeting_records=meeting_records,
        )

    @staticmethod
    def _request(url: str, params: dict[str, str | int]) -> dict:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
