from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch

from lib.llm.valueobject.completion import ChatResult, RoleType
from lib.llm.valueobject.config import OpenAIGptConfig
from llm_chat.domain.use_case.completion.riddle import RiddleUseCase
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    GenderType,
    SessionState,
    RiddleTurnEvaluation,
)
from llm_chat.models import RiddleQuestion


class RiddleSessionStateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_user")
        self.config = OpenAIGptConfig(api_key="test", model="gpt-4o", max_tokens=1000)
        self.gender = Gender(GenderType.MAN)

        # テスト用の問題を3つ登録
        for i in range(1, 4):
            RiddleQuestion.objects.create(
                question_text=f"問題{i}", answer_text=f"正解{i}", order=i
            )

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_user_message_is_persisted(self, mock_retrieve):
        """
        USER メッセージが DB に保存され、next_riddle_state が正しく設定されていることを確認。
        """
        mock_retrieve.return_value = ChatResult(
            answer="こんにちは！質問1です", explanation=""
        )
        use_case = RiddleUseCase(self.config)

        # 1. 実行
        use_case.execute(self.user, "スタート", self.gender)

        # 2. DB を確認
        from llm_chat.models import ChatLogs

        logs = ChatLogs.objects.filter(user=self.user).order_by("created_at")

        # スタート時は USER, ASSISTANT の 2 つのログができるはず
        self.assertEqual(logs.count(), 2)

        user_log = logs[0]
        assistant_log = logs[1]

        self.assertEqual(user_log.role, RoleType.USER.value)
        self.assertEqual(assistant_log.role, RoleType.ASSISTANT.value)

        # USER ログにも next_riddle_state が入っていること (START のみ)
        self.assertEqual(user_log.next_riddle_state, SessionState.START.value)
        # ASSISTANT ログには START, USER_INPUT が入っているはず
        self.assertIn(SessionState.START.value, assistant_log.next_riddle_state)
        self.assertIn(SessionState.USER_INPUT.value, assistant_log.next_riddle_state)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_session_state_transition(self, mock_retrieve):
        """
        シナリオ:
        - 入力: ユーザーからの「回答1」などのメッセージ。
        - 期待値: 適切な状態遷移が行われること。
        """
        # LLMの回答をモック（終了メッセージを含まない）
        mock_retrieve.return_value = ChatResult(answer="感想です", explanation="")

        # テスト用の問題をたくさん登録（終了判定を回避するため）
        for i in range(4, 20):
            RiddleQuestion.objects.create(
                question_text=f"問題{i}", answer_text=f"正解{i}", order=i
            )

        # max_turnsを大きくして終了しないようにする
        use_case = RiddleUseCase(self.config, max_turns=15)

        # 1. スタート (None/START -> USER_INPUT)
        res1 = use_case.execute(self.user, "スタート", self.gender)
        # ユーザーログは START, アシスタントログは START, USER_INPUT が含まれるはず
        self.assertIn(SessionState.START.value, res1.next_riddle_state)
        self.assertIn(SessionState.USER_INPUT.value, res1.next_riddle_state)

        # 2. 回答1 (USER_INPUT -> [USER_INPUT, EVALUATE] -> EVALUATE -> USER_INPUT)
        res2 = use_case.execute(self.user, "回答1", self.gender)
        # ASSISTANT ログには EVALUATE が含まれるはず
        self.assertIn(SessionState.EVALUATE.value, res2.next_riddle_state)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_question_2_user_input_transition(self, mock_retrieve):
        """
        質問2が出された直後の next_riddle_state は EVALUATE,USER_INPUT であるべき。
        """
        # 回答1への感想と、質問2の出題。
        mock_retrieve.return_value = ChatResult(
            answer="回答ありがとうございます。素晴らしいですね。\n\n##### 質問2\n私は黒い服を着て、赤い手袋を持っている...",
            explanation="",
        )

        use_case = RiddleUseCase(self.config, max_turns=3)

        # 1. スタート
        res1 = use_case.execute(self.user, "スタート", self.gender)
        self.assertIn(SessionState.USER_INPUT.value, res1.next_riddle_state)

        # 2. 回答1 -> 質問2出題
        res2 = use_case.execute(self.user, "人間", self.gender)

        # インジケータとして EVALUATE と USER_INPUT の両方が含まれていることを確認
        states = res2.next_riddle_state.split(",")
        self.assertIn(SessionState.EVALUATE.value, states)
        self.assertIn(SessionState.USER_INPUT.value, states)
        # 順番も重要
        self.assertEqual(
            states, [SessionState.EVALUATE.value, SessionState.USER_INPUT.value]
        )

    @patch("llm_chat.domain.service.completion.riddle.RiddleChatService.evaluate_turn")
    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_session_finished_state(self, mock_retrieve, mock_turn_eval):
        """
        シナリオ:
        - 入力: 終了定型文を含むLLMの回答。
        - 処理: RiddleUseCase.execute を呼び出し、セッション終了判定を確認する。
        - 期待値: 最終的な next_riddle_state が FINISHED（終了）状態であること。
        """
        # 終了定型文を含む回答をモック
        from llm_chat.domain.service.completion.riddle import RiddleChatService

        # 1回目の回答（開始時）
        start_response = ChatResult(answer="こんにちは！質問1です", explanation="")
        # 2回目の回答（終了時）
        end_response = ChatResult(
            answer=f"正解です！\n\n{RiddleChatService.RIDDLE_END_MESSAGE}",
            explanation="",
        )
        mock_retrieve.side_effect = [start_response, end_response]
        mock_turn_eval.return_value = RiddleTurnEvaluation(
            correctness=3, reasoning=0, creativity=0, rebuttal=0
        )

        use_case = RiddleUseCase(self.config)

        # 1問しかないので、スタートの後の回答で終了するはず
        use_case.execute(self.user, "スタート", self.gender)
        res = use_case.execute(self.user, "フライパン", self.gender)

        self.assertIn(SessionState.FINISHED.value, res.next_riddle_state)
        self.assertIn(SessionState.EVALUATE.value, res.next_riddle_state)
