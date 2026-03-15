from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.models import ChatLogs, RiddleQuestion
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import Gender, GenderType
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

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_extra_question_removal(self, mock_retrieve):
        """
        [シナリオ: なぞなぞ終了時の余計な質問除去]
        1. LLMが規定回数終了時に「第3問」を出題しようとするケースを模倣
        2. RiddleUseCase.execute() を実行
        3. 期待値:
           - 「第3問」以降が除去され、終了定型文で終わっていること
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
            )
        )
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.ASSISTANT,
                content="第2問...",
                use_case_type=UseCaseType.RIDDLE,
            )
        )

        # LLMの回答を模倣（余計な第3問を含む）
        assistant_content = (
            "正解です！たいまつで合っています。\n"
            "では第3問です。\n"
            "僕は呼吸をするけど生きていない...\n"
            f"ご回答をどうぞ。\n\n"
            f"{RiddleChatService.RIDDLE_END_MESSAGE}"
        )
        # 1回目の呼び出し（回答生成）と2回目の呼び出し（評価生成）
        mock_retrieve.side_effect = [
            MagicMock(answer=assistant_content),
            MagicMock(
                answer='{"correctness": 3, "reasoning": 4, "creativity": 2, "rebuttal": 0, "comment": "テスト"}'
            ),
        ]

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        result = use_case.execute(self.user, "答え2", gender=Gender(GenderType.MAN))

        # 「第3問」や「僕は呼吸をするけど...」が消えていることを確認
        self.assertIn("正解です！たいまつで合っています。", result.content)
        self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
        self.assertNotIn("第3問", result.content)
        self.assertNotIn("僕は呼吸をするけど", result.content)
        self.assertIn("正確性: 3/5", result.content)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_end_detection_invalid_json(self, mock_retrieve):
        """
        [シナリオ: なぞなぞ終了判定（不正なJSON）]
        1. LLM の回答がリスト形式だが中身が文字列であるケースを模倣
        2. RiddleUseCase.execute() を実行
        3. 期待値:
           - TypeError を起こさず、空の評価結果で終了すること
        """
        # 不正なJSON（リストの中に文字列）を模倣
        mock_retrieve.return_value = MagicMock(answer='["invalid", "string", "items"]')

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        # 3回目のユーザー発言相当のコンテキストを作る
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
                content="質問1...",
                use_case_type=UseCaseType.RIDDLE,
            )
        )
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.USER,
                content="答え1",
                use_case_type=UseCaseType.RIDDLE,
            )
        )
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.ASSISTANT,
                content="質問2...",
                use_case_type=UseCaseType.RIDDLE,
            )
        )

        # evaluate 内部での LLM 実行（評価 JSON 取得）がこの mock_retrieve を使う
        result = use_case.execute(
            self.user, "答えはたいまつです", gender=Gender(GenderType.MAN)
        )

        self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
        self.assertIn("評価結果のパースに失敗しました", result.content)
        self.assertEqual(result.use_case_type, UseCaseType.RIDDLE)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_end_detection(self, mock_retrieve):
        """
        [シナリオ: なぞなぞ終了判定]
        1. LLM の回答に終了キーワード (RIDDLE_END_MESSAGE) が含まれるケースを模倣
        2. RiddleUseCase.execute() を実行
        3. 期待値:
           - 回答内容に終了メッセージが含まれていること
           - 回答後の評価結果が含まれていること
           - メッセージの use_case_type が UseCaseType.RIDDLE であること
        """
        # 終了メッセージを含む回答を模倣
        mock_retrieve.return_value = MagicMock(
            answer=f"正解です！ {RiddleChatService.RIDDLE_END_MESSAGE}"
        )

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        # RiddleUseCase.execute は内部で evaluate を呼ぶ（さらに LLM 実行）
        with patch(
            "llm_chat.domain.service.completion.chat.ChatService.evaluate"
        ) as mock_eval:
            mock_eval.return_value = "\n【評価結果】\n- 正確性: 5/5"

            result = use_case.execute(
                self.user, "答えは人間です", gender=Gender(GenderType.MAN)
            )

            self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
            self.assertIn("評価結果", result.content)
            self.assertEqual(result.use_case_type, UseCaseType.RIDDLE)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_forced_end(self, mock_retrieve):
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

        # 過去に2回ユーザー発言がある状態を作る（今回で3回目）
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
                content="質問1...",
                use_case_type=UseCaseType.RIDDLE,
            )
        )
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.USER,
                content="答え1",
                use_case_type=UseCaseType.RIDDLE,
            )
        )
        ChatLogRepository.insert(
            MessageDTO(
                user=self.user,
                role=RoleType.ASSISTANT,
                content="質問2...",
                use_case_type=UseCaseType.RIDDLE,
            )
        )

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        with patch(
            "llm_chat.domain.service.completion.chat.ChatService.evaluate"
        ) as mock_eval:
            mock_eval.return_value = "\n【評価結果】\n- 評価1: 100点"

            # 3回目のユーザー発言
            result = use_case.execute(
                self.user, "それはたいまつです", gender=Gender(GenderType.MAN)
            )

            self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
            self.assertIn("評価結果", result.content)
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
