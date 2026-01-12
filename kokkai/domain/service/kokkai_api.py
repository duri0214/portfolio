import requests
from datetime import date
from ..valueobject.meeting import MeetingSearchResult, MeetingRecord, SpeechRecord


class KokkaiAPIClient:
    BASE_URL = "https://kokkai.ndl.go.jp/api/meeting"

    def search_meetings(
        self, start_date: date, end_date: date, start_record: int = 1
    ) -> MeetingSearchResult:
        """
        指定された期間の会議一覧を取得する。
        """
        params = {
            "from": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d"),
            "startRecord": start_record,
            "maximumRecords": 10,
            "recordPacking": "json",
        }

        response = requests.get(self.BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        meeting_records = []
        for record in data.get("meetingRecord", []):
            speech_records = []
            for s in record.get("speechRecord", []):
                speech_records.append(
                    SpeechRecord(
                        speech_id=s["speechID"],
                        speaker=s["speaker"],
                        speaker_yomi=s.get("speakerYomi"),
                        speaker_group=s.get("speakerGroup"),
                        speaker_position=s.get("speakerPosition"),
                        speaker_role=s.get("speakerRole"),
                        speech=s.get("speech"),
                        speech_order=s["speechOrder"],
                        start_page=s.get("startPage"),
                        create_time=s["createTime"],
                        update_time=s["updateTime"],
                        speech_url=s["speechURL"],
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
            number_of_return_records=data.get("numberOfReturnRecords", 0),
            start_record=data.get("startRecord", 1),
            next_record_position=data.get("nextRecordPosition"),
            meeting_records=meeting_records,
        )
