from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from kokkai.domain.service.scenario import OpenAIScenarioGenerator, ScenarioService
from kokkai.models import (
    Meeting,
    MeetingScenario,
    ScenarioActor,
    ScenarioChoice,
    ScenarioPlay,
    ScenarioTurn,
    Speech,
)


class FakeScenarioGenerator:
    """シナリオ生成サービスの入力とキャッシュを検証するテストダブル。"""

    model = "test-scenario-model"

    def __init__(self) -> None:
        self.calls = []

    def generate(self, meeting, actors, source_chunks):
        self.calls.append((meeting, actors, source_chunks))
        return {
            "title": "予算委員会シミュレーション",
            "background": "予算案を審議する会議を基にしたシミュレーションです。",
            "success_label": "適切",
            "failure_label": "不適切",
            "judgment_criteria": "根拠発言に沿う選択を半数以上行うこと。",
            "passing_score": 50,
            "turns": [
                {
                    "actor_key": actors[0]["key"],
                    "dialogue": "論点を確認します。",
                    "evidence_speech_order": 1,
                    "evidence_note": "最初の発言で論点が示されています。",
                    "choices": [
                        {
                            "text": "論点に沿って回答する",
                            "is_correct": True,
                            "rationale": "発言の論点を踏まえています。",
                        },
                        {
                            "text": "別の話題に移す",
                            "is_correct": False,
                            "rationale": "根拠発言の論点と異なります。",
                        },
                    ],
                },
                {
                    "actor_key": actors[-1]["key"],
                    "dialogue": "次の確認事項です。",
                    "evidence_speech_order": 2,
                    "evidence_note": "二つ目の発言が確認事項の根拠です。",
                    "choices": [
                        {
                            "text": "資料の確認を求める",
                            "is_correct": True,
                            "rationale": "発言内容に沿う確認です。",
                        },
                        {
                            "text": "根拠なく結論を急ぐ",
                            "is_correct": False,
                            "rationale": "発言内容に根拠がありません。",
                        },
                    ],
                },
            ],
        }


class PartialScenarioGenerator(FakeScenarioGenerator):
    """重要なアクターだけを返すテスト用ジェネレーター。"""

    def generate(self, meeting, actors, source_chunks):
        generated = super().generate(meeting, actors, source_chunks)
        generated["turns"] = generated["turns"][:1]
        return generated


class OpenAIScenarioGeneratorTests(SimpleTestCase):
    def test_long_meeting_chunks_are_summarized_and_aggregated_in_bounded_groups(self):
        """
        シナリオ:
        - 入力: 上限より一つ多い数の会議録入力単位。
        - 実行: 段階的な入力単位の要約・集約を行う。
        - 期待結果: 全文を一つの巨大入力にせず、最終集約前の要約数を上限以内にする。
        """
        generator = OpenAIScenarioGenerator(api_key="test-key")
        client = Mock()
        client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content='{"events": []}'))]
        )
        source_chunks = [f"[speech_order: {index}]\n発言本文" for index in range(13)]

        summaries = generator._summarize_source_chunks(client, source_chunks)

        self.assertEqual(len(summaries), 2)
        self.assertEqual(client.chat.completions.create.call_count, 15)
        for call in client.chat.completions.create.call_args_list:
            messages = call.kwargs["messages"]
            self.assertTrue(
                any("json" in str(message["content"]) for message in messages)
            )


class ScenarioServiceTests(TestCase):
    def setUp(self):
        self.meeting = Meeting.objects.create(
            meeting_date="2024-01-26",
            session_number=213,
            house="衆議院",
            committee="予算委員会",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://kokkai.ndl.go.jp/txt/121305254X00120240126",
        )
        Speech.objects.create(
            meeting=self.meeting,
            speaker_name="議員A",
            speaker_role="委員",
            speaker_affiliation="会派A",
            speech_text="予算案の根拠を確認します。",
            speech_order=1,
            source_url="https://kokkai.ndl.go.jp/txt/121305254X00120240126/1",
        )
        Speech.objects.create(
            meeting=self.meeting,
            speaker_name="大臣B",
            speaker_role="大臣",
            speaker_affiliation="政府",
            speech_text="資料に基づき説明します。",
            speech_order=2,
            source_url="https://kokkai.ndl.go.jp/txt/121305254X00120240126/2",
        )
        self.generator = FakeScenarioGenerator()
        self.service = ScenarioService(generator=self.generator)

    def test_get_or_create_reuses_a_matching_saved_scenario_without_regeneration(self):
        """
        シナリオ:
        - 入力: 同じ会議録・発言データ・プロンプトバージョンで二度作成を要求する。
        - 実行: get_or_create を二度呼び出す。
        - 期待結果: 生成は一度だけで、保存済みシナリオと根拠付きターンが再利用される。
        """
        scenario, created = self.service.get_or_create(self.meeting)
        reused_scenario, reused = self.service.get_or_create(self.meeting)

        self.assertTrue(created)
        self.assertFalse(reused)
        self.assertEqual(scenario.pk, reused_scenario.pk)
        self.assertEqual(len(self.generator.calls), 1)
        self.assertEqual(MeetingScenario.objects.count(), 1)
        self.assertEqual(scenario.actors.count(), 2)
        self.assertEqual(scenario.turns.count(), 2)
        self.assertEqual(
            scenario.turns.first().evidence_speech.source_url,
            "https://kokkai.ndl.go.jp/txt/121305254X00120240126/1",
        )
        self.assertIn("[speech_order: 1]", self.generator.calls[0][2][0])

    def test_regenerate_preserves_the_existing_scenario_as_a_new_version(self):
        """
        シナリオ:
        - 入力: 保存済みのシナリオがある会議録。
        - 実行: 明示的な regenerate を呼び出す。
        - 期待結果: 旧バージョンを上書きせず、次のバージョンを保存する。
        """
        first_scenario, _ = self.service.get_or_create(self.meeting)
        regenerated_scenario = self.service.regenerate(self.meeting)

        self.assertEqual(len(self.generator.calls), 2)
        self.assertEqual(MeetingScenario.objects.count(), 2)
        self.assertEqual(first_scenario.version, 1)
        self.assertEqual(regenerated_scenario.version, 2)

    def test_scenario_uses_only_actors_that_appear_in_generated_turns(self):
        """
        シナリオ:
        - 入力: 会議録上の全アクターのうち、主要アクターだけを返す生成結果。
        - 処理: シナリオを生成して保存する。
        - 期待値: ターンのないアクターをプレイ対象にせず、生成が失敗しないこと。
        """
        service = ScenarioService(generator=PartialScenarioGenerator())

        scenario, created = service.get_or_create(self.meeting)

        self.assertTrue(created)
        self.assertEqual(scenario.actors.count(), 1)
        self.assertEqual(scenario.turns.count(), 1)

    def test_meeting_metadata_record_is_not_used_for_scenario_or_display(self):
        """
        シナリオ:
        - 入力: 実際の発言に加えて、国会APIの「会議録情報」メタデータ行がある会議録。
        - 処理: シナリオ生成と会議詳細表示を行う。
        - 期待値: メタデータ行をアクターや画面の会議録本文として扱わないこと。
        """
        Speech.objects.create(
            meeting=self.meeting,
            speaker_name="会議録情報",
            speech_text="会議の日時などのメタデータ",
            speech_order=0,
        )

        scenario, _ = self.service.get_or_create(self.meeting)
        response = self.client.get(
            reverse("kokkai:meeting_detail", args=[self.meeting.pk])
        )

        self.assertEqual(scenario.actors.count(), 2)
        self.assertNotContains(response, "会議の日時などのメタデータ")

    def test_availability_marks_a_scenario_for_regeneration_after_speech_changes(self):
        """
        シナリオ:
        - 入力: 生成済みシナリオと、その後に更新された発言本文。
        - 実行: 会議詳細用の利用可否を取得する。
        - 期待結果: 自動再生成せず、要再生成として返す。
        """
        self.service.get_or_create(self.meeting)
        speech = self.meeting.speeches.get(speech_order=2)
        speech.speech_text = "資料の根拠を追加して説明します。"
        speech.save(update_fields=["speech_text"])

        availability = self.service.get_availability(self.meeting)

        self.assertTrue(availability.needs_regeneration)
        self.assertEqual(len(self.generator.calls), 1)

    def test_meeting_detail_contains_generation_loading_feedback(self):
        """
        シナリオ:
        - 入力: 本文を取り込んだ会議録の詳細画面。
        - 実行: シナリオ作成フォームを表示する。
        - 期待結果: 生成中のスピナー・不定プログレスバー用のUIが含まれる。
        """
        response = self.client.get(
            reverse("kokkai:meeting_detail", args=[self.meeting.pk])
        )

        self.assertContains(response, "progress-bar-animated")
        self.assertContains(response, "シナリオを生成中")
        self.assertContains(response, 'value="create_scenario"')

    def test_meeting_detail_collapses_source_speeches_before_scenario_exists(self):
        """
        シナリオ:
        - 入力: まだシナリオを作成していない本文取得済み会議録。
        - 処理: 会議詳細画面を表示する。
        - 期待値: 原文は初期表示で折りたたまれ、必要なときだけ確認できること。
        """
        response = self.client.get(
            reverse("kokkai:meeting_detail", args=[self.meeting.pk])
        )

        self.assertContains(response, "会議録の原文を確認する")
        self.assertContains(response, "<details")

    def test_meeting_detail_collapses_source_speeches_after_scenario_exists(self):
        """
        シナリオ:
        - 入力: シナリオを保存済みの会議録詳細画面。
        - 処理: 詳細画面を表示する。
        - 期待値: 原文は折りたたまれ、必要なときだけ確認できること。
        """
        self.service.get_or_create(self.meeting)

        response = self.client.get(
            reverse("kokkai:meeting_detail", args=[self.meeting.pk])
        )

        self.assertContains(response, "会議録の原文を確認する")
        self.assertContains(response, "<details")


class ScenarioGameViewTests(TestCase):
    def setUp(self):
        self.meeting = Meeting.objects.create(
            meeting_date="2024-01-26",
            session_number=213,
            house="衆議院",
            committee="予算委員会",
            meeting_number="第1号",
            min_id="121305254X00120240127",
            url="https://kokkai.ndl.go.jp/txt/121305254X00120240127",
        )
        self.first_speech = Speech.objects.create(
            meeting=self.meeting,
            speaker_name="大臣B",
            speech_text="政府として資料を提示します。",
            speech_order=1,
            source_url="https://kokkai.ndl.go.jp/txt/121305254X00120240127/1",
        )
        self.second_speech = Speech.objects.create(
            meeting=self.meeting,
            speaker_name="議員A",
            speech_text="資料の根拠を確認します。",
            speech_order=2,
            source_url="https://kokkai.ndl.go.jp/txt/121305254X00120240127/2",
        )
        self.scenario = MeetingScenario.objects.create(
            meeting=self.meeting,
            version=1,
            source_hash="a" * 64,
            prompt_version="meeting-simulation-v1",
            generator_model="test-scenario-model",
            title="保存済みシナリオ",
            background="会議録を基にしたシミュレーションです。",
            success_label="成立",
            failure_label="不成立",
            judgment_criteria="根拠発言に沿って選択すること。",
            passing_score=50,
        )
        self.other_actor = ScenarioActor.objects.create(
            scenario=self.scenario,
            display_order=1,
            name="大臣B",
            speech_count=1,
        )
        self.player_actor = ScenarioActor.objects.create(
            scenario=self.scenario,
            display_order=2,
            name="議員A",
            speech_count=1,
        )
        first_turn = ScenarioTurn.objects.create(
            scenario=self.scenario,
            turn_number=1,
            actor=self.other_actor,
            dialogue="資料を提示します。",
            evidence_speech=self.first_speech,
            evidence_note="大臣の一次発言です。",
        )
        self.player_turn = ScenarioTurn.objects.create(
            scenario=self.scenario,
            turn_number=2,
            actor=self.player_actor,
            dialogue="根拠を確認します。",
            evidence_speech=self.second_speech,
            evidence_note="議員の一次発言です。",
        )
        ScenarioChoice.objects.create(
            turn=first_turn,
            choice_number=1,
            text="自動進行用の選択肢",
            is_correct=True,
            rationale="他アクターのターンです。",
        )
        self.correct_choice = ScenarioChoice.objects.create(
            turn=self.player_turn,
            choice_number=1,
            text="資料の根拠を確認する",
            is_correct=True,
            rationale="会議録の論点に沿っています。",
        )
        ScenarioChoice.objects.create(
            turn=self.player_turn,
            choice_number=2,
            text="別の話題に移る",
            is_correct=False,
            rationale="会議録の論点に沿っていません。",
        )

    def test_saved_turns_progress_to_a_result_without_openai_or_embedding_calls(self):
        """
        シナリオ:
        - 入力: 保存済みのシナリオで議員Aを担当に選ぶ。
        - 実行: 他アクターの発言を進め、二択を一つ選択する。
        - 期待結果: APIを呼ばずに結果画面へ進み、根拠発言へのリンクを表示する。
        """
        actor_select_url = reverse(
            "kokkai:scenario_actor_select", args=[self.scenario.pk]
        )
        with patch("kokkai.domain.service.scenario.OpenAI") as mock_openai:
            response = self.client.post(
                actor_select_url, {"actor_id": self.player_actor.pk}
            )
            play = ScenarioPlay.objects.get()
            game_url = reverse("kokkai:scenario_game", args=[play.play_id])
            self.client.post(game_url, {"action": "next"})
            game_response = self.client.get(game_url)
            self.assertContains(game_response, "choice-deck")
            self.assertContains(game_response, "左右にスワイプ")
            response = self.client.post(
                game_url,
                {"action": "answer", "choice_id": self.correct_choice.pk},
            )

        result_url = reverse("kokkai:scenario_result", args=[play.play_id])
        self.assertRedirects(response, result_url)
        self.assertFalse(mock_openai.called)
        result_response = self.client.get(result_url)
        self.assertContains(result_response, "成立")
        self.assertContains(
            result_response,
            "https://kokkai.ndl.go.jp/txt/121305254X00120240127/2",
        )
