from unittest import TestCase
from unittest.mock import MagicMock, patch

from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import ModelDefaults, OpenAIGptConfig


class LlmCompletionConfigTest(TestCase):
    @patch("lib.llm.service.completion.OpenAI")
    def test_structured_request_forwards_profile_reasoning_and_format(
        self, mock_openai
    ):
        """
        シナリオ:
        - 入力: 推論設定付きのKokkaiプロファイルとJSON応答形式。
        - 処理: 共通完了サービスで1件のチャット回答を生成する。
        - 期待値: モデル、reasoning_effort、response_formatが同じAPIリクエストへ渡される。
        """
        mock_client = mock_openai.return_value
        mock_client.chat.completions.create.return_value = MagicMock(
            model=ModelDefaults.KOKKAI_SCENARIO.model,
            choices=[
                MagicMock(
                    message=MagicMock(content='{"overview": "summary"}'),
                    finish_reason="stop",
                )
            ],
            usage=None,
        )
        service = LlmCompletionService(
            OpenAIGptConfig.from_profile(
                ModelDefaults.KOKKAI_SCENARIO,
                api_key="test-key",
                max_tokens=4000,
            )
        )

        result = service.retrieve_answer(
            [Message(role=RoleType.SYSTEM, content="JSON only")],
            max_messages=1,
            response_format={"type": "json_object"},
        )

        request = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], ModelDefaults.KOKKAI_SCENARIO.model)
        self.assertEqual(request["reasoning_effort"], "low")
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertEqual(result.answer, '{"overview": "summary"}')
