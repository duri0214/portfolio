from datetime import date
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from openai import OpenAIError

from kokkai.domain.service.scenario import (
    OpenAIScenarioGenerator,
    ScenarioGenerationError,
    ScenarioService,
)
from kokkai.domain.valueobject.scenario import ScenarioActorData
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
        self.choice_calls = []

    def generate(self, meeting, actors, source_chunks):
        self.calls.append((meeting, actors, source_chunks))
        return {
            "title": "予算委員会シミュレーション",
            "background": "予算案を審議する会議を基にしたシミュレーションです。",
            "success_label": "適切",
            "failure_label": "不適切",
            "judgment_criteria": "根拠発言に沿う選択を半数以上行うこと。",
            "passing_score": 50,
        }

    def generate_choices(self, meeting, actor, speech, background):
        self.choice_calls.append((meeting, actor, speech, background))
        return {
            "choices": [
                {
                    "text": "発言の論点に沿って答える",
                    "is_correct": True,
                    "rationale": "会議録の発言内容に沿っています。",
                },
                {
                    "text": "根拠なく別の話題へ移る",
                    "is_correct": False,
                    "rationale": "会議録の発言内容から外れています。",
                },
            ]
        }


class InvalidScoreScenarioGenerator(FakeScenarioGenerator):
    """数値ではない合格点を返すテスト用ジェネレーター。"""

    def generate(self, meeting, actors, source_chunks):
        generated = super().generate(meeting, actors, source_chunks)
        generated["passing_score"] = "invalid"
        return generated


class OpenAIScenarioGeneratorTests(SimpleTestCase):
    def test_generate_sends_the_transcript_once_for_the_overview(self):
        """
        シナリオ:
        - 入力: 複数の発言単位を含む会議録と、概要生成用のOpenAIクライアント。
        - 実行: 会議全体の概要生成を呼び出す。
        - 期待結果: 中間要約を挟まず、会議全体を1回のリクエストで渡す。
        """
        generator = OpenAIScenarioGenerator(api_key="test-key")
        client = Mock()
        client.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"background": "会議全体の要約", "passing_score": 50}'
                    )
                )
            ]
        )
        meeting = Meeting(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="予算委員会",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://example.com/meeting",
        )
        source_chunks = [
            "[speech_order: 1]\n冒頭の発言",
            "[speech_order: 21]\n後半の発言",
        ]

        with patch("kokkai.domain.service.scenario.OpenAI", return_value=client):
            generated = generator.generate(meeting, [], source_chunks)

        self.assertEqual(generated["background"], "会議全体の要約")
        client.chat.completions.create.assert_called_once()
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["model"],
            "gpt-4o-mini",
        )
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        user_content = messages[1]["content"]
        self.assertLess(
            user_content.index("speech_order: 1"),
            user_content.index("speech_order: 21"),
        )
        self.assertNotIn('"turns"', user_content)

    def test_generate_choices_uses_only_the_current_actor_speech(self):
        """
        シナリオ:
        - 入力: 会議全体の要約と、選択アクターの現在の発言。
        - 実行: 発言単位の二択生成を呼び出す。
        - 期待値: 現在の発言を根拠にした二択を1回だけ要求する。
        """
        generator = OpenAIScenarioGenerator(api_key="test-key")
        client = Mock()
        client.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"choices": [{"text": "A", "is_correct": true}, {"text": "B", "is_correct": false}]}'
                    )
                )
            ]
        )
        meeting = Meeting(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="予算委員会",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://example.com/meeting",
        )
        actor = ScenarioActorData(
            key="actor-1",
            display_order=1,
            name="議員A",
            role="委員",
            affiliation="会派A",
            speech_count=1,
        )
        speech = Speech(
            meeting=meeting,
            speaker_name="議員A",
            speaker_role="委員",
            speaker_affiliation="会派A",
            speech_text="資料の根拠を確認します。",
            speech_order=21,
            source_url="https://example.com/meeting/21",
        )

        with patch("kokkai.domain.service.scenario.OpenAI", return_value=client):
            generated = generator.generate_choices(
                meeting, actor, speech, "会議全体の要約"
            )

        self.assertEqual(len(generated["choices"]), 2)
        client.chat.completions.create.assert_called_once()
        user_content = client.chat.completions.create.call_args.kwargs["messages"][1][
            "content"
        ]
        self.assertIn("speech_order", user_content)
        self.assertIn("21", user_content)
        self.assertIn("資料の根拠を確認します。", user_content)

    def test_openai_request_error_is_converted_to_scenario_generation_error(self):
        """
        シナリオ:
        - 入力: OpenAI SDK がリクエスト例外を返す生成クライアント。
        - 処理: JSON出力を要求する。
        - 期待値: SDK例外を画面で扱えるシナリオ生成例外へ変換する。
        """
        generator = OpenAIScenarioGenerator(api_key="test-key")
        client = Mock()
        client.chat.completions.create.side_effect = OpenAIError("network error")

        with self.assertRaises(ScenarioGenerationError):
            generator._request_json_content(
                client,
                [{"role": "system", "content": "Return valid json only."}],
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
        self.assertEqual(self.generator.choice_calls, [])
        self.assertEqual(MeetingScenario.objects.count(), 1)
        self.assertEqual(scenario.actors.count(), 2)
        self.assertEqual(scenario.turns.count(), 3)
        self.assertEqual(
            list(
                scenario.turns.values_list(
                    "turn_number", "is_overview", "evidence_speech__speech_order"
                )
            ),
            [(1, True, None), (2, False, 1), (3, False, 2)],
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

    def test_scenario_uses_all_speech_actors_and_defers_choice_generation(self):
        """
        シナリオ:
        - 入力: 複数アクターの発言を含む会議録。
        - 処理: 会議全体のシナリオを生成して保存する。
        - 期待値: 全発言をNo.順に保存し、選択肢生成はプレイ開始時まで行わない。
        """
        scenario, created = self.service.get_or_create(self.meeting)

        self.assertTrue(created)
        self.assertEqual(scenario.actors.count(), 2)
        self.assertEqual(scenario.turns.count(), 3)
        self.assertEqual(self.generator.choice_calls, [])

    def test_invalid_passing_score_falls_back_to_the_default(self):
        """
        シナリオ:
        - 入力: 数値ではない合格点を含む生成結果。
        - 処理: シナリオを正規化して保存する。
        - 期待値: 例外にせず、既定の合格点50を保存する。
        """
        service = ScenarioService(generator=InvalidScoreScenarioGenerator())

        scenario, created = service.get_or_create(self.meeting)

        self.assertTrue(created)
        self.assertEqual(scenario.passing_score, 50)

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
        self.assertContains(
            response,
            "会議録全体を要約し、原文の発言を議事録 No.順にたどりながら、担当する役割としてどう対応するかを選ぶ教育用ロールプレイです。",
        )
        self.assertNotContains(response, "実在人物が実際に発言した内容ではありません。")

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
            prompt_version="meeting-simulation-v2",
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
        ScenarioTurn.objects.create(
            scenario=self.scenario,
            turn_number=1,
            is_overview=True,
            dialogue="会議録全体の要約です。",
            evidence_note="会議録全体を見渡した要約です。",
        )
        ScenarioTurn.objects.create(
            scenario=self.scenario,
            turn_number=2,
            actor=self.other_actor,
            dialogue="資料を提示します。",
            evidence_speech=self.first_speech,
            evidence_note="大臣の一次発言です。",
        )
        self.player_turn = ScenarioTurn.objects.create(
            scenario=self.scenario,
            turn_number=3,
            actor=self.player_actor,
            dialogue="根拠を確認します。",
            evidence_speech=self.second_speech,
            evidence_note="議員の一次発言です。",
        )

    def test_transcript_progresses_in_order_and_generates_choices_only_for_player(self):
        """
        シナリオ:
        - 入力: 全体要約、他アクターのNo.1、担当アクターのNo.2を持つシナリオ。
        - 実行: No.順に進め、担当アクターの発言で二択を生成して回答する。
        - 期待結果: 要約と発言が順番に表示され、二択生成は担当アクターの発言だけで1回行われる。
        """
        actor_select_url = reverse(
            "kokkai:scenario_actor_select", args=[self.scenario.pk]
        )
        generator = FakeScenarioGenerator()
        with patch(
            "kokkai.domain.service.scenario_play.OpenAIScenarioGenerator",
            return_value=generator,
        ):
            response = self.client.post(
                actor_select_url, {"actor_id": self.player_actor.pk}
            )
            play = ScenarioPlay.objects.get()
            game_url = reverse("kokkai:scenario_game", args=[play.play_id])
            overview_response = self.client.get(game_url)
            self.assertContains(overview_response, "会議全体の要約")
            self.assertContains(overview_response, "全体要約")
            self.assertEqual(generator.choice_calls, [])

            self.client.post(game_url, {"action": "next"})
            first_response = self.client.get(game_url)
            self.assertContains(first_response, "議事録 No.001")
            self.assertContains(first_response, "資料を提示します。")
            self.assertFalse(first_response.context["is_player_turn"])

            self.client.post(game_url, {"action": "next"})
            game_response = self.client.get(game_url)
            self.assertContains(game_response, "choice-deck")
            self.assertContains(game_response, "クリックして返答を選びます")
            self.assertContains(game_response, "議事録 No.002")
            self.assertContains(game_response, "choice-card-flash")
            self.assertContains(
                game_response, "HTMLFormElement.prototype.submit.call(form)"
            )
            self.assertNotContains(game_response, "スワイプ")
            self.assertContains(
                game_response,
                "会議録全体の要約から始まり、原文の発言を議事録 No.順に表示します。",
            )
            self.assertEqual(len(generator.choice_calls), 1)
            self.assertEqual(generator.choice_calls[0][2].speech_order, 2)
            correct_choice = ScenarioChoice.objects.get(
                turn=self.player_turn, is_correct=True
            )
            response = self.client.post(
                game_url,
                {"action": "answer", "choice_id": correct_choice.pk},
            )

        result_url = reverse("kokkai:scenario_result", args=[play.play_id])
        self.assertRedirects(response, result_url)
        result_response = self.client.get(result_url)
        self.assertContains(result_response, "成立")
        self.assertContains(
            result_response,
            "https://kokkai.ndl.go.jp/txt/121305254X00120240127/2",
        )
