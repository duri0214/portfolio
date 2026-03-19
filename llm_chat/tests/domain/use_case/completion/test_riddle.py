from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.models import ChatLogs, RiddleQuestion
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    GenderType,
    SessionState,
    RiddleTurnEvaluation,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.use_case.completion.riddle import RiddleUseCase
from llm_chat.domain.repository.completion.chat import ChatLogRepository


class RiddleUseCaseTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="logic_user")
        # デフォルトの問題を登録
        RiddleQuestion.objects.create(
            question_text="はじめは4本足、途中から2本足、最後は3本足。それは何でしょう？",
            answer_text="人間",
            order=1,
        )
        RiddleQuestion.objects.create(
            question_text="私は黒い服を着て、赤い手袋を持っている。夜には立っているが、朝になると寝る。何でしょう？",
            answer_text="たいまつ",
            order=2,
        )

    def test_get_chat_history_riddle_first(self):
        """
        [シナリオ: なぞなぞ初回開始]
        1. 過去の履歴がない状態で、ユーザーメッセージ (use_case_type=UseCaseType.RIDDLE) を受け取る
        2. get_chat_history(use_case_type=UseCaseType.RIDDLE) を実行
        3. 期待値:
           - 内部的にシステムメッセージが生成され、履歴リストの先頭に追加されること (計2通)
           - ユーザーメッセージのみが DB に保存されること
        """
        user_message = MessageDTO(
            user=self.user,
            role=RoleType.USER,
            content="なぞなぞスタート",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
        )
        # 初回：システムメッセージ（非保存）と初回ユーザーメッセージ（保存）
        history = ChatService.get_chat_history(
            user_message,
            use_case_type=UseCaseType.RIDDLE,
            gender=Gender(GenderType.MAN),
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].role, RoleType.SYSTEM)
        self.assertEqual(history[1].role, RoleType.USER)
        self.assertEqual(history[1].use_case_type, UseCaseType.RIDDLE)

        # DBには初回ユーザーメッセージが保存されているはず
        db_logs = ChatLogs.objects.filter(user=self.user)
        self.assertEqual(db_logs.count(), 1)
        self.assertEqual(db_logs[0].role, RoleType.USER.value)

    @patch("llm_chat.domain.service.completion.riddle.RiddleChatService.evaluate_turn")
    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_extra_question_removal(
        self, mock_retrieve, mock_turn_eval
    ):
        """
        [シナリオ: なぞなぞ終了時の余計な質問・継続提案の除去]
        1. LLMが規定回数終了時に「第3問」や「続けて別のなぞなぞを...」を出そうとするケースを模倣
        2. RiddleUseCase.execute() を実行
        3. 期待値:
           - 余計なパターンが除去され、終了定型文で終わっていること
        """
        # ユーザーの発言を蓄積（3回目の発言＝2問目への回答を想定）
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.USER,
                content="スタート",
                use_case_type=UseCaseType.RIDDLE,
            )
        )
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.ASSISTANT,
                content="第1問...",
                use_case_type=UseCaseType.RIDDLE,
            )
        )
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.USER,
                content="答え1",
                use_case_type=UseCaseType.RIDDLE,
                next_riddle_state=SessionState.USER_INPUT.value,
            )
        )
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.ASSISTANT,
                content="第2問...",
                use_case_type=UseCaseType.RIDDLE,
                next_riddle_state=SessionState.USER_INPUT.value,
            )
        )

        # LLMの回答を模倣（余計な第3問と継続提案を含む）
        assistant_content = (
            "正解です！たいまつで合っています。\n"
            "では\n"
            "第3問です。\n"
            "僕は呼吸をするけど生きていない...\n"
            "続けて別のなぞなぞを出しましょうか？\n"
            f"ご回答をどうぞ。\n\n"
            f"{RiddleChatService.RIDDLE_END_MESSAGE}"
        )
        mock_retrieve.return_value = MagicMock(answer=assistant_content)
        mock_turn_eval.return_value = RiddleTurnEvaluation(
            correctness=3, reasoning=4, creativity=2, rebuttal=0
        )

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        result = use_case.execute(self.user, "答え2", gender=Gender(GenderType.MAN))

        # 「第3問」や継続提案が消えていることを確認
        self.assertIn("正解です！たいまつで合っています。", result.content)
        self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
        self.assertNotIn("第3問", result.content)
        self.assertNotIn("続けて別のなぞなぞを出しましょうか？", result.content)
        self.assertIn("あなたの回答傾向", result.content)

    @patch("llm_chat.domain.service.completion.riddle.RiddleChatService.evaluate_turn")
    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_end_detection_invalid_json(
        self, mock_retrieve, mock_turn_eval
    ):
        """
        [シナリオ: なぞなぞ終了判定（不正なJSON）]
        1. LLM の回答がリスト形式だが中身が文字列であるケースを模倣
        2. RiddleUseCase.execute() を実行
        3. 期待値:
           - TypeError を起こさず、空の評価結果で終了すること
        """
        # 不正なJSON（リストの中に文字列）を模倣
        mock_retrieve.side_effect = [
            MagicMock(answer="質問1..."),
            MagicMock(answer="質問2..."),
            MagicMock(answer=f"正解です！ {RiddleChatService.RIDDLE_END_MESSAGE}"),
        ]
        mock_turn_eval.return_value = RiddleTurnEvaluation(
            correctness=3, reasoning=0, creativity=0, rebuttal=0
        )

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        # 1. スタート（ここで履歴がクリアされ、新しいセッションが始まる）
        use_case.execute(self.user, "スタート", gender=Gender(GenderType.MAN))

        # 2. 1問目の回答（状態は USER_INPUT へ）
        use_case.execute(self.user, "答え1", gender=Gender(GenderType.MAN))

        # 3. 2問目の回答（ここで終了判定）
        result = use_case.execute(
            self.user, "答えはたいまつです", gender=Gender(GenderType.MAN)
        )

        self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
        self.assertIn("あなたの回答傾向", result.content)
        self.assertEqual(result.use_case_type, UseCaseType.RIDDLE)

    @patch("llm_chat.domain.service.completion.riddle.RiddleChatService.evaluate_turn")
    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_end_detection(self, mock_retrieve, mock_turn_eval):
        """
        [シナリオ: なぞなぞ終了判定]
        1. LLM の回答に終了キーワード (RIDDLE_END_MESSAGE) が含まれるケースを模倣
        2. RiddleUseCase.execute() を実行
        3. 期待値:
           - 回答内容に終了メッセージが含まれていること
           - 回答後の評価結果が含まれていること
           - メッセージの use_case_type が UseCaseType.RIDDLE であること
        """
        # 1回目は普通の回答、2回目は終了メッセージを含む回答
        mock_retrieve.side_effect = [
            MagicMock(answer="こんにちは！質問1です。"),
            MagicMock(answer=f"正解です！ {RiddleChatService.RIDDLE_END_MESSAGE}"),
        ]

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        mock_turn_eval.return_value = RiddleTurnEvaluation(
            correctness=3, reasoning=0, creativity=0, rebuttal=0
        )

        # 1回目：スタート（ここで状態が USER_INPUT に遷移する）
        use_case.execute(self.user, "スタート", gender=Gender(GenderType.MAN))

        # 2回目：終了を模倣した回答
        result = use_case.execute(
            self.user, "答えは人間です", gender=Gender(GenderType.MAN)
        )

        self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
        self.assertIn("あなたの回答傾向", result.content)
        self.assertEqual(result.use_case_type, UseCaseType.RIDDLE)

    @patch("llm_chat.domain.repository.completion.chat.ChatLogRepository.clear_all")
    @patch("llm_chat.domain.service.completion.riddle.RiddleChatService.evaluate_turn")
    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_forced_end(
        self, mock_retrieve, mock_turn_eval, mock_clear
    ):
        """
        [シナリオ: なぞなぞ強制終了]
        1. LLM の回答に終了キーワードが含まれないが、3回目の発言（質問2への回答）である場合
        2. RiddleUseCase.execute() を実行
        3. 期待値:
           - 回答内容に終了メッセージが強制的に追加されていること
           - 評価結果が含まれていること
        """
        # 終了メッセージを含まない回答
        mock_retrieve.return_value = MagicMock(
            answer="それはたいまつですね。正解です！"
        )

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        mock_turn_eval.return_value = RiddleTurnEvaluation(
            correctness=3, reasoning=0, creativity=0, rebuttal=0
        )

        # 1回目：スタート（ここでのアシスタント回答の最後は USER_INPUT）
        use_case.execute(self.user, "スタート", gender=Gender(GenderType.MAN))

        # 2回目：回答1（ここでのアシスタント回答の最後も USER_INPUT）
        use_case.execute(self.user, "答え1", gender=Gender(GenderType.MAN))

        # 3回目のユーザー発言（ここで終了判定）
        result = use_case.execute(
            self.user, "それはたいまつです", gender=Gender(GenderType.MAN)
        )

        self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
        self.assertIn("あなたの回答傾向", result.content)
        self.assertEqual(result.use_case_type, UseCaseType.RIDDLE)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_normal(self, mock_retrieve):
        """
        [シナリオ: なぞなぞユースケース]
        1. RiddleUseCase を使用してなぞなぞを開始
        2. 期待値:
           - 回答内容が取得され、use_case_type が UseCaseType.RIDDLE であること
           - ユーザーとアシスタントの計2通が DB に保存されること (システムメッセージは保存されない)
        """
        mock_retrieve.return_value = MagicMock(answer="それは人間ですか？")
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)
        result = use_case.execute(self.user, "スタート", gender=Gender(GenderType.MAN))

        self.assertEqual(result.content, "それは人間ですか？")
        self.assertEqual(result.use_case_type, UseCaseType.RIDDLE)
        # 初回なぞなぞ：System(非保存), User, Assistant の計2通がDBへ
        self.assertEqual(ChatLogs.objects.filter(user=self.user).count(), 2)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_reset_on_start(self, mock_retrieve):
        """
        [シナリオ: なぞなぞ開始時に履歴がリセットされることの検証]
        1. 既に履歴がある状態で「なぞなぞを始めて」と送る。
        2. 期待値: 履歴が一旦クリアされ、新しいセッション（User, Assistant）の2件のみになること。
        """
        mock_retrieve.return_value = MagicMock(answer="なぞなぞを始めます。")
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        # 1. 適当な履歴を作成
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.USER,
                content="古い会話",
                use_case_type=UseCaseType.OPENAI_GPT,
            )
        )
        self.assertEqual(ChatLogs.objects.filter(user=self.user).count(), 1)

        # 2. なぞなぞ開始（リセットされるはず）
        use_case.execute(self.user, "なぞなぞを始めて", gender=Gender(GenderType.MAN))

        # 古い会話が消え、新しい User, Assistant の2件のみになっているはず
        db_logs = ChatLogs.objects.filter(user=self.user)
        self.assertEqual(db_logs.count(), 2)
        self.assertEqual(db_logs[0].content, "なぞなぞを始めて")

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_no_reset_on_answer(self, mock_retrieve):
        """
        [シナリオ: 2問目以降の回答で履歴が保持されることの検証]
        1. なぞなぞを開始し、1問目の回答を送る。
        2. 期待値: 履歴が保持され、ChatLogs が累積していくこと。
        """
        mock_retrieve.return_value = MagicMock(answer="正解です。次は2問目です。")
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        # 1. なぞなぞ開始
        use_case.execute(self.user, "なぞなぞを始めて", gender=Gender(GenderType.MAN))
        self.assertEqual(
            ChatLogs.objects.filter(user=self.user).count(), 2
        )  # User, Assistant

        # 2. 1問目の回答 (ChatService側での暗黙のリセットがなくなったため、常に累積する)
        use_case.execute(self.user, "答えは人間です", gender=Gender(GenderType.MAN))
        # 履歴がリセットされなければ、User(初回), Assistant(初回), User(2回目), Assistant(2回目) で 4件になる
        self.assertEqual(ChatLogs.objects.filter(user=self.user).count(), 4)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_no_questions_raises_error(self, mock_retrieve):
        """
        [シナリオ: 問題が未登録の場合の挙動]
        1. RiddleQuestion をすべて削除
        2. RiddleUseCase.execute() を実行
        3. 期待値: ValueError が発生し、適切なメッセージが返されること
        """
        RiddleQuestion.objects.all().delete()
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        with self.assertRaisesRegex(
            ValueError,
            "なぞなぞの問題が登録されていません。管理画面から問題を登録してください。",
        ):
            use_case.execute(self.user, "スタート", gender=Gender(GenderType.MAN))

    def test_get_chat_history_riddle_no_gender_raises_error(self):
        """
        [シナリオ] なぞなぞモードで性別を指定せずに get_chat_history を呼び出す
        [期待値] ValueError が発生すること
        """
        user_message = MessageDTO(
            user=self.user,
            role=RoleType.USER,
            content="なぞなぞスタート",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
        )
        with self.assertRaisesRegex(ValueError, "gender is required for RiddleUseCase"):
            ChatService.get_chat_history(
                user_message, use_case_type=UseCaseType.RIDDLE, gender=None
            )

    def test_riddle_use_case_no_gender_raises_error(self):
        """
        [シナリオ] RiddleUseCase.execute を性別指定なしで呼び出す
        [期待値] ValueError が発生すること
        """
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)
        with self.assertRaisesRegex(ValueError, "gender is required for RiddleUseCase"):
            use_case.execute(user=self.user, content="なぞなぞスタート", gender=None)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_finished_session_raises_error(self, mock_retrieve):
        """
        [シナリオ: 終了済みセッションでの発言]
        1. セッションが既に FINISHED 状態である。
        2. 開始信号（スタート等）を含まないメッセージを送信する。
        3. 期待値: ValueError が発生し、再開を促すメッセージが返されること。
        """
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)
        gender = Gender(GenderType.MAN)

        # 1. 履歴に FINISHED 状態のメッセージを挿入
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.ASSISTANT,
                content="なぞなぞ終了です。",
                use_case_type=UseCaseType.RIDDLE,
                next_riddle_state=SessionState.to_csv([SessionState.FINISHED]),
            )
        )

        # 2. 開始信号なしでメッセージ送信
        with self.assertRaisesRegex(
            ValueError,
            "セッションが終了しています。画面上の「なぞなぞの開始」を押してやりなおしてください。",
        ):
            use_case.execute(self.user, "こんにちは", gender=gender)

        # 3. 開始信号があれば通ること（リセットされること）を確認
        mock_retrieve.return_value = MagicMock(answer="新しく始めます。")
        use_case.execute(self.user, "スタート", gender=gender)
        self.assertEqual(ChatLogs.objects.filter(user=self.user).count(), 2)
