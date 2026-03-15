from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch

from lib.llm.valueobject.completion import ChatResult
from lib.llm.valueobject.config import OpenAIGptConfig
from llm_chat.domain.use_case.completion.riddle import RiddleUseCase
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    GenderType,
    SessionState,
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
    def test_session_state_transition(self, mock_retrieve):
        """
        シナリオ:
        - 入力: ユーザーからの「スタート」、「回答1」、「反論」のメッセージ。
        - 処理: RiddleUseCase.execute を順次呼び出し、セッション状態の遷移を確認する。
        - 期待値:
            1. 「スタート」後: WAIT_ANSWER（回答待ち）状態であること。
            2. 「回答1」後: EVALUATE（評価中）状態であること。
            3. 「反論」後: WAIT_REBUTTAL（反論待ち）状態であること。
        """
        # LLMの回答をモック
        mock_retrieve.return_value = ChatResult(answer="感想です", explanation="")

        use_case = RiddleUseCase(self.config)

        # 1. スタート
        res1 = use_case.execute(self.user, "スタート", self.gender)
        # スタート時は ASK_QUESTION -> WAIT_ANSWER に遷移しているはず
        self.assertEqual(res1.riddle_state, SessionState.WAIT_ANSWER.value)

        # 2. 回答1
        res2 = use_case.execute(self.user, "回答1", self.gender)
        # WAIT_ANSWER -> EVALUATE に遷移しているはず
        self.assertEqual(res2.riddle_state, SessionState.EVALUATE.value)

        # 3. 反論（現在の簡易ロジックでは EVALUATE の次は WAIT_REBUTTAL になるはず）
        res3 = use_case.execute(self.user, "いや、違います", self.gender)
        self.assertEqual(res3.riddle_state, SessionState.WAIT_REBUTTAL.value)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_session_finished_state(self, mock_retrieve):
        """
        シナリオ:
        - 入力: 終了定型文を含むLLMの回答。
        - 処理: RiddleUseCase.execute を呼び出し、セッション終了判定を確認する。
        - 期待値: 最終的な riddle_state が FINISHED（終了）状態であること。
        """
        # 終了定型文を含む回答をモック
        from llm_chat.domain.service.completion.riddle import RiddleChatService

        mock_retrieve.return_value = ChatResult(
            answer=f"正解です！\n\n{RiddleChatService.RIDDLE_END_MESSAGE}",
            explanation="",
        )

        use_case = RiddleUseCase(self.config)

        # 1問しかないので、スタートの後の回答で終了するはず
        use_case.execute(self.user, "スタート", self.gender)
        res = use_case.execute(self.user, "フライパン", self.gender)

        self.assertEqual(res.riddle_state, SessionState.FINISHED.value)
