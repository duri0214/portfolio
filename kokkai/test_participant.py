from dataclasses import replace
from datetime import date

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from kokkai.domain.repository.participant_repository import MeetingParticipantRepository
from kokkai.domain.service.participant import (
    MeetingParticipantExtractor,
    normalize_person_name,
)
from kokkai.domain.service.participant_query import ParticipantQueryService
from kokkai.domain.valueobject.meeting import MeetingRecord, SpeechRecord
from kokkai.models import Meeting, MeetingParticipant, MeetingParticipantEvidence


def participant_meeting_record() -> MeetingRecord:
    """出席欄と複数の発言を持つテスト用会議録を返す。"""

    issue_id = "121305254X00120240126"
    metadata = SpeechRecord(
        speech_id=f"{issue_id}_000",
        speaker="会議録情報",
        speaker_yomi=None,
        speaker_group=None,
        speaker_position=None,
        speaker_role=None,
        speech=(
            "令和六年一月二十六日（金曜日）\n"
            "出席委員\n"
            "　　　委員長　藤丸　　敏君\n"
            "　　　理事　上野賢一郎君　理事　古賀　　篤君\n"
            "　　　　　　安藤たかお君　　　　石橋林太郎君\n"
            "　　　　…………………………………\n"
            "　　　政府参考人\n"
            "　　　（内閣府政策統括官）　　　水野　　敦君\n"
            "　　　（デジタル庁審議官）　　　三浦　　明君\n"
            "　　　　―――――――――――――\n"
            "委員の異動\n"
            "　　　異動のみ議員君"
        ),
        speech_order=0,
        start_page=1,
        create_time="2024-01-26T00:00:00",
        update_time="2024-01-26T00:00:00",
        speech_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}/0",
    )
    speeches = [
        SpeechRecord(
            speech_id=f"{issue_id}_001",
            speaker="藤丸敏",
            speaker_yomi="ふじまるさとし",
            speaker_group="会派A",
            speaker_position="委員長",
            speaker_role=None,
            speech="開会します。",
            speech_order=1,
            start_page=1,
            create_time="2024-01-26T00:00:00",
            update_time="2024-01-26T00:00:00",
            speech_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}/1",
        ),
        SpeechRecord(
            speech_id=f"{issue_id}_002",
            speaker="藤丸敏",
            speaker_yomi="ふじまるさとし",
            speaker_group="会派A",
            speaker_position="委員長",
            speaker_role=None,
            speech="議題を確認します。",
            speech_order=2,
            start_page=1,
            create_time="2024-01-26T00:00:00",
            update_time="2024-01-26T00:00:00",
            speech_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}/2",
        ),
        SpeechRecord(
            speech_id=f"{issue_id}_003",
            speaker="石破茂",
            speaker_yomi="いしばしげる",
            speaker_group="会派B",
            speaker_position=None,
            speaker_role="参考人",
            speech="説明します。",
            speech_order=3,
            start_page=1,
            create_time="2024-01-26T00:00:00",
            update_time="2024-01-26T00:00:00",
            speech_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}/3",
        ),
        SpeechRecord(
            speech_id=f"{issue_id}_004",
            speaker="上野賢一郎",
            speaker_yomi="うえのけんいちろう",
            speaker_group="会派A",
            speaker_position="理事",
            speaker_role=None,
            speech="答弁します。",
            speech_order=4,
            start_page=1,
            create_time="2024-01-26T00:00:00",
            update_time="2024-01-26T00:00:00",
            speech_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}/4",
        ),
    ]
    return MeetingRecord(
        issue_id=issue_id,
        image_kind="会議録",
        search_object=0,
        session=213,
        name_of_house="衆議院",
        name_of_meeting="本会議",
        issue="第1号",
        date=date(2024, 1, 26).isoformat(),
        closing=None,
        speech_records=[metadata, *speeches],
        meeting_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}",
        pdf_url=None,
    )


class MeetingParticipantExtractorTests(SimpleTestCase):
    def test_uses_attendees_as_the_participant_source_of_truth(self):
        """
        シナリオ:
        - 入力: 出席者一覧メタデータと、複数回発言した人物・発言者のみの人物を含む会議録。
        - 処理: 会議録参加者抽出サービスを実行する。
        - 期待値: 出席者一覧だけを参加者とし、発言者のみの人物は追加しない。
        """
        participants = MeetingParticipantExtractor().extract(
            participant_meeting_record()
        )

        self.assertEqual(
            [participant.name for participant in participants],
            [
                "藤丸敏",
                "上野賢一郎",
                "古賀篤",
                "安藤たかお",
                "石橋林太郎",
                "水野敦",
                "三浦明",
            ],
        )
        chair = participants[0]
        self.assertEqual(chair.attendance_type, "chair")
        self.assertEqual(chair.attendance_role, "委員長")
        self.assertTrue(chair.has_spoken)
        self.assertEqual(chair.speech_count, 2)
        self.assertEqual(chair.speaker_position, "委員長")
        self.assertEqual(chair.affiliation, "会派A")
        self.assertEqual(participants[4].attendance_type, "committee_member")
        self.assertFalse(participants[4].has_spoken)
        self.assertEqual(participants[5].attendance_type, "government_reference")
        self.assertFalse(participants[5].has_spoken)
        self.assertEqual(participants[6].attendance_type, "government_reference")
        self.assertFalse(participants[6].has_spoken)
        self.assertTrue(participants[1].has_spoken)
        self.assertEqual(participants[1].speech_count, 1)
        self.assertNotIn("石破茂", [participant.name for participant in participants])

    def test_normalizes_honorifics_and_full_width_spaces(self):
        """
        シナリオ:
        - 入力: 全角空白と公式会議録で使われる敬称を含む氏名。
        - 処理: 氏名正規化関数を呼び出す。
        - 期待値: 表記ゆれを除いた突合用の氏名が返る。
        """
        self.assertEqual(normalize_person_name("藤丸　　敏君"), "藤丸敏")
        self.assertEqual(
            normalize_person_name("（内閣府政策統括官）　水野　敦君"), "水野敦"
        )

    def test_normalizes_government_and_staff_titles_in_attendance_lines(self):
        """
        シナリオ:
        - 入力: 大臣、国務大臣、国家公安委員会委員長、専門員の出席欄。
        - 処理: 会議録参加者抽出サービスを実行する。
        - 期待値: 肩書きを氏名へ混在させず、出席種別と役職を保持する。
        """
        record = participant_meeting_record()
        metadata = record.speech_records[0]
        metadata = replace(
            metadata,
            speech=metadata.speech.replace(
                "　　　政府参考人\n",
                "　　　内閣総理大臣　　　　　高市　早苗君\n"
                "　　　総務大臣　　　　　　　林　　芳正君\n"
                "　　　財務副大臣　　　　　　中谷　真一君\n"
                "　　　国務大臣\n"
                "　　　（国家公安委員会委員長）　あかま二郎君\n"
                "　　　予算委員会専門員　　　　藤井　宏治君\n"
                "　　　政府参考人\n",
                1,
            ),
        )
        record = replace(record, speech_records=[metadata, *record.speech_records[1:]])

        participants = MeetingParticipantExtractor().extract(record)
        participants_by_name = {
            participant.name: participant for participant in participants
        }

        self.assertEqual(
            participants_by_name["高市早苗"].attendance_type,
            "government_official",
        )
        self.assertEqual(participants_by_name["林芳正"].attendance_role, "総務大臣")
        self.assertEqual(
            participants_by_name["中谷真一"].attendance_type,
            "government_official",
        )
        self.assertEqual(
            participants_by_name["あかま二郎"].attendance_role,
            "国家公安委員会委員長",
        )
        self.assertEqual(participants_by_name["藤井宏治"].attendance_type, "staff")
        self.assertNotIn("総務大臣林芳正", participants_by_name)


class MeetingParticipantRepositoryTests(TestCase):
    def setUp(self):
        self.meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="本会議",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://kokkai.ndl.go.jp/txt/121305254X00120240126",
        )
        self.participants = MeetingParticipantExtractor().extract(
            participant_meeting_record()
        )

    def test_replace_for_meeting_is_idempotent_and_preserves_evidence(self):
        """
        シナリオ:
        - 入力: 同じ会議録から抽出した参加者一覧を2回保存する。
        - 処理: 会議参加者Repositoryの洗い替えを繰り返す。
        - 期待値: 参加者・根拠が重複せず、発言数と根拠URLを保持する。
        """
        repository = MeetingParticipantRepository()

        repository.replace_for_meeting(self.meeting, self.participants)
        repository.replace_for_meeting(self.meeting, self.participants)

        self.assertEqual(
            MeetingParticipant.objects.filter(meeting=self.meeting).count(), 7
        )
        self.assertEqual(
            MeetingParticipantEvidence.objects.filter(
                participant__meeting=self.meeting
            ).count(),
            10,
        )
        chair = MeetingParticipant.objects.get(meeting=self.meeting, name="藤丸敏")
        self.assertEqual(chair.speech_count, 2)
        self.assertEqual(chair.evidences.filter(source_type="speech").count(), 2)
        self.assertTrue(
            chair.evidences.filter(
                source_speech_id="121305254X00120240126_001"
            ).exists()
        )

    def test_actor_candidates_prioritize_speakers_and_speech_count(self):
        """
        シナリオ:
        - 入力: 発言あり・出席のみの参加者を保存した会議録。
        - 処理: シナリオ連携用のアクター候補を取得する。
        - 期待値: 発言者を先に並べ、発言数の多い人物を優先する。
        """
        MeetingParticipantRepository().replace_for_meeting(
            self.meeting, self.participants
        )

        candidates = ParticipantQueryService().get_actor_candidates(self.meeting)

        self.assertEqual(
            [candidate.name for candidate in candidates[:2]], ["藤丸敏", "上野賢一郎"]
        )
        self.assertTrue(all(candidate.has_spoken for candidate in candidates[:2]))
        self.assertEqual(candidates[0].speech_count, 2)
        self.assertNotIn("石破茂", [candidate.name for candidate in candidates])

    def test_list_participants_prioritizes_speakers_and_speech_count(self):
        """
        シナリオ:
        - 入力: 出席者と、複数回・1回発言した参加者を含む会議録。
        - 処理: 会議詳細用の参加者一覧を取得する。
        - 期待値: 発言者を先頭にし、発言回数の多い順で表示する。
        """
        MeetingParticipantRepository().replace_for_meeting(
            self.meeting, self.participants
        )

        participants = list(ParticipantQueryService().list_participants(self.meeting))

        self.assertEqual(
            [participant.name for participant in participants[:2]],
            ["藤丸敏", "上野賢一郎"],
        )
        self.assertTrue(all(participant.has_spoken for participant in participants[:2]))
        self.assertFalse(participants[2].has_spoken)

    def test_participant_summary_counts_attendance_and_speakers_separately(self):
        """
        シナリオ:
        - 入力: 出席欄の7人と、出席者2人・出席者でない1人の発言を含む会議録。
        - 処理: 会議参加者の集計を取得する。
        - 期待値: 出席者数と、出席者のうち発言した人数を別々に数える。
        """
        MeetingParticipantRepository().replace_for_meeting(
            self.meeting, self.participants
        )

        summary = ParticipantQueryService().get_participant_summary(self.meeting)

        self.assertEqual(summary.attendance_count, 7)
        self.assertEqual(summary.committee_member_count, 5)
        self.assertEqual(summary.non_committee_attendance_count, 2)
        self.assertEqual(summary.speaker_count, 2)

    def test_meeting_detail_displays_participant_status_and_evidence(self):
        """
        シナリオ:
        - 入力: 出席者と発言者を含む参加者データを保存した会議録。
        - 処理: 会議詳細画面を表示する。
        - 期待値: 出席のみ・発言数・根拠会議録IDと出典リンクを確認できる。
        """
        MeetingParticipantRepository().replace_for_meeting(
            self.meeting, self.participants
        )

        response = self.client.get(
            reverse("kokkai:meeting_detail", args=[self.meeting.pk])
        )

        self.assertContains(response, "会議参加者")
        self.assertContains(response, "出席のみ")
        self.assertContains(response, "発言あり")
        self.assertContains(response, "出席委員数: 5人")
        self.assertContains(response, "その他出席者数: 2人")
        self.assertContains(response, "出席者総数: 7人")
        self.assertContains(response, "ユニーク発言者数: 2人")
        self.assertNotContains(response, "統合参加者数")
        self.assertContains(response, "会議録ID: 121305254X00120240126")
        self.assertContains(response, "出典")
