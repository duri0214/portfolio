from unittest import TestCase

from django.contrib.auth.models import User

from lib.llm.llm_service import count_tokens, cut_down_chat_history
from lib.llm.valueobject.chat import RoleType
from lib.llm.valueobject.config import (
    OpenAIGptConfig,
    validate_temperature,
)
from llm_chat.domain.valueobject.chat import MessageDTO


class TestLlmService(TestCase):
    def setUp(self):
        test_user, created = User.objects.get_or_create(
            username="test-user",
            defaults={"email": "test@example.com", "password": "test-password"},
        )
        if created:
            test_user.set_password("test-password")

        self.chat_history = [
            MessageDTO(
                content="Hello",
                role=RoleType.USER,
                invisible=False,
                user=test_user,
            ),
            MessageDTO(
                content=", ",
                role=RoleType.ASSISTANT,
                invisible=False,
                user=test_user,
            ),
            MessageDTO(
                content="world!",
                role=RoleType.USER,
                invisible=False,
                user=test_user,
            ),
        ]

    def test_count_tokens(self):
        token_count = count_tokens("こんにちは、世界!")
        self.assertIsInstance(token_count, int, "token_count は整数であるはずです")
        self.assertGreater(token_count, 0, "token_count は0より大きいはずです")

        token_count_empty = count_tokens("")
        self.assertEqual(token_count_empty, 0, "token_count は0であるはずです")

    def test_cut_down_chat_history(self):
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=100, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history(self.chat_history, config)
        self.assertIsInstance(cut_history, list, "cut_history はリストであるはずです")
        self.assertEqual(len(cut_history), 3, "すべてのメッセージが残るべきです")

    def test_cut_down_chat_history_with_less_max_tokens(self):
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=2, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history(self.chat_history, config)
        self.assertEqual(len(cut_history), 1, "最新のメッセージだけが残るべきです")
        self.assertEqual(cut_history[0].content, "world!", "メッセージ内容が正しいこと")

    def test_cut_down_chat_history_empty(self):
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=100, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history([], config)
        self.assertEqual(cut_history, [], "空のリストであるはずです")


class TestValidateTemperature(TestCase):
    def test_valid_temperature(self):
        # Test that valid temperatures do not raise error
        for temp in [0, 0.5, 1]:
            result = validate_temperature(temp)
            self.assertEqual(result, temp)

    def test_invalid_temperature(self):
        # Test that temperatures out of range raise ValueError
        for temp in [-1, 1.5]:
            with self.assertRaises(ValueError):
                validate_temperature(temp)
