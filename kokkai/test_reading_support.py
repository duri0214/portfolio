from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from kokkai.domain.service.reading_support import ReadingSupportService
from kokkai.domain.valueobject.reading_support import (
    ReadingOverride,
    ReadingSupportDictionary,
    TermDefinition,
)
from kokkai.models import (
    Meeting,
    MeetingScenario,
    ScenarioActor,
    ScenarioPlay,
    ScenarioTurn,
    Speech,
)


class ReadingSupportServiceTests(SimpleTestCase):
    """読み仮名と登録用語の解析結果を検証する。"""

    def setUp(self):
        self.service = ReadingSupportService()

    def test_annotation_preserves_text_and_corrects_os_hakari_reading(self):
        """
        シナリオ:
        - 入力: 「お諮り」、通常の漢字語、固有名詞を含む本文。
        - 処理: ReadingSupportService で本文を解析する。
        - 期待値: 原文を失わず、「お諮り」は自然な読みになり、固有名詞は断定的に読まれない。
        """
        text = "お諮りします。会議録を確認します。山田太郎。"

        annotation = self.service.annotate(text)

        self.assertEqual("".join(segment.text for segment in annotation.segments), text)
        self.assertEqual(
            next(
                segment.reading
                for segment in annotation.segments
                if segment.text == "お諮り"
            ),
            "おはかり",
        )
        self.assertEqual(
            [
                segment.reading
                for segment in annotation.segments
                if segment.text in {"会議", "録"}
            ],
            ["カイギ", "ロク"],
        )
        self.assertFalse(
            any(
                segment.reading
                for segment in annotation.segments
                if segment.text in {"山田", "太郎"}
            )
        )

    def test_annotation_detects_foip_with_width_case_and_space_variations(self):
        """
        シナリオ:
        - 入力: 全角、大文字の空白区切り、半角小文字で表記した FOIP。
        - 処理: 表記を正規化して登録用語を検出する。
        - 期待値: 3つすべてが同じ用語定義に紐づき、原文の表記は保持される。
        """
        text = "ＦＯＩＰ、F O I P、foip"

        annotation = self.service.annotate(text)
        terms = [segment for segment in annotation.segments if segment.term]

        self.assertEqual(
            [segment.text for segment in terms], ["ＦＯＩＰ", "F O I P", "foip"]
        )
        self.assertTrue(all(segment.term.surface == "FOIP" for segment in terms))
        self.assertTrue(
            all(
                segment.term.source_url
                == "https://www.meti.go.jp/policy/external_economy/trade/foip/index.html"
                for segment in terms
            )
        )

    def test_annotation_leaves_unregistered_words_as_plain_text(self):
        """
        シナリオ:
        - 入力: 登録辞書にないカタカナ語と本文。
        - 処理: 読み仮名・用語解析を実行する。
        - 期待値: 例外を発生させず、未登録語を推測表示しない。
        """
        text = "ハノイカルコイカイ"

        annotation = self.service.annotate(text)

        self.assertEqual("".join(segment.text for segment in annotation.segments), text)
        self.assertFalse(annotation.has_support)

    def test_service_uses_one_dictionary_for_terms_and_reading_overrides(self):
        """
        シナリオ:
        - 入力: 用語と読み補正を登録した読み仮名支援辞書。
        - 処理: 同じ辞書をReadingSupportServiceへ渡して本文を解析する。
        - 期待値: 用語と読み補正の両方が、辞書の登録内容から表示される。
        """
        dictionary = ReadingSupportDictionary(
            terms=(
                TermDefinition(
                    surface="NISA",
                    reading="ニーサ",
                    description="少額投資非課税制度",
                    category="制度",
                    source_url="https://example.com/nisa",
                ),
            ),
            reading_overrides=(
                ReadingOverride(surface="読み補正", reading="ヨミホセイ"),
            ),
        )

        annotation = ReadingSupportService(dictionary=dictionary).annotate(
            "読み補正とNISAを確認します。"
        )

        self.assertEqual(
            next(
                segment.reading
                for segment in annotation.segments
                if segment.text == "読み補正"
            ),
            "ヨミホセイ",
        )
        self.assertEqual(
            next(
                segment.term.surface
                for segment in annotation.segments
                if segment.text == "NISA"
            ),
            "NISA",
        )

    def test_annotation_ignores_empty_overrides_and_keeps_overlapping_text_once(self):
        """
        シナリオ:
        - 入力: 空の読み補正と、同じ位置で重なる2つの読み補正を含む辞書。
        - 処理: 辞書を使って本文を解析する。
        - 期待値: 空の補正は無視し、長い補正を1回だけ適用して原文を重複させない。
        """
        dictionary = ReadingSupportDictionary(
            terms=(),
            reading_overrides=(
                ReadingOverride(surface="", reading="空"),
                ReadingOverride(surface="AB", reading="エービー"),
                ReadingOverride(surface="ABC", reading="エービーシー"),
            ),
        )

        annotation = ReadingSupportService(dictionary=dictionary).annotate("ABC")

        self.assertEqual(
            [(segment.text, segment.reading) for segment in annotation.segments],
            [("ABC", "エービーシー")],
        )
        self.assertEqual(
            "".join(segment.text for segment in annotation.segments), "ABC"
        )


class ReadingSupportViewTests(TestCase):
    """会議詳細とシナリオ画面で学習補助を確認できることを検証する。"""

    def setUp(self):
        self.meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="予算委員会",
            meeting_number="第1号",
            min_id="reading-support-meeting",
            url="https://kokkai.ndl.go.jp/txt/reading-support-meeting",
        )

    def test_meeting_detail_exposes_readings_and_term_sources(self):
        """
        シナリオ:
        - 入力: 「お諮り」と全角表記の FOIP を含む会議録本文。
        - 処理: 会議詳細画面を表示する。
        - 期待値: 原文に加えて読み確認欄、読み、用語説明、公式出典リンクが表示される。
        """
        Speech.objects.create(
            meeting=self.meeting,
            speaker_name="議員A",
            speech_text="お諮りします。ＦＯＩＰについて確認します。",
            speech_order=1,
            source_url="https://kokkai.ndl.go.jp/txt/reading-support-meeting/1",
        )

        response = self.client.get(
            reverse("kokkai:meeting_detail", args=[self.meeting.pk])
        )

        self.assertContains(response, "お諮りします。ＦＯＩＰについて確認します。")
        self.assertContains(response, "読み仮名・用語を確認")
        self.assertContains(response, "おはかり")
        self.assertContains(
            response,
            '<ruby class="kokkai-reading">お諮り<rt>おはかり</rt></ruby>します。',
        )
        self.assertContains(
            response,
            'します。<details class="kokkai-term d-inline"><summary',
        )
        self.assertContains(response, "Free and Open Indo-Pacific")
        self.assertContains(response, "公式資料で確認する")
        self.assertContains(response, "https://janome.mocobeta.dev/ja/")
        self.assertContains(
            response, "登録した読み補正と用語の読みは読み仮名支援辞書に基づきます"
        )

    def test_scenario_game_exposes_learning_support_for_the_current_speech(self):
        """
        シナリオ:
        - 入力: 他アクターの現在発言に「お諮り」と FOIP を含む保存済みシナリオ。
        - 処理: シナリオゲームの現在ターンを表示する。
        - 期待値: ゲーム進行を変更せず、現在発言から読み仮名と用語説明を確認できる。
        """
        scenario = MeetingScenario.objects.create(
            meeting=self.meeting,
            version=1,
            source_hash="b" * 64,
            prompt_version="meeting-simulation-v2",
            generator_model="test-scenario-model",
            title="保存済みシナリオ",
            overview="会議録全体の要約です。",
            success_label="成立",
            failure_label="不成立",
            judgment_criteria="根拠発言に沿って選択すること。",
        )
        other_actor = ScenarioActor.objects.create(
            scenario=scenario,
            display_order=1,
            name="大臣B",
            speech_count=1,
        )
        player_actor = ScenarioActor.objects.create(
            scenario=scenario,
            display_order=2,
            name="議員A",
            speech_count=1,
        )
        speech = Speech.objects.create(
            meeting=self.meeting,
            speaker_name="大臣B",
            speech_text="お諮りします。ＦＯＩＰを確認します。",
            speech_order=1,
        )
        ScenarioTurn.objects.create(
            scenario=scenario,
            turn_number=1,
            actor=other_actor,
            dialogue=speech.speech_text,
            evidence_speech=speech,
            evidence_note="大臣の一次発言です。",
        )
        play = ScenarioPlay.objects.create(
            scenario=scenario,
            selected_actor=player_actor,
        )

        with patch(
            "kokkai.domain.service.scenario_play.OpenAIScenarioGenerator"
        ) as generator_class:
            response = self.client.get(
                reverse("kokkai:scenario_game", args=[play.play_id])
            )

        self.assertContains(response, "読み仮名・用語を確認")
        self.assertContains(response, "おはかり")
        self.assertContains(response, "Free and Open Indo-Pacific")
        generator_class.return_value.generate.assert_not_called()
        generator_class.return_value.generate_choices.assert_not_called()
        play.refresh_from_db()
        self.assertEqual(play.next_turn_number, 1)
