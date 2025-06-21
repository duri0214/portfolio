from django.test import TestCase

from lib.llm.service.completion import count_tokens, cut_down_chat_history
from lib.llm.valueobject.chat import RoleType, Message
from lib.llm.valueobject.config import OpenAIGptConfig, validate_temperature


class TestLlmService(TestCase):
    """
    LLMサービス関連の関数をテストするためのテストケース。

    対象とする関数:
        - count_tokens: テキストのトークン数をカウントする関数。
        - cut_down_chat_history: チャット履歴をトークン数制限に基づいて削減する関数。
    """

    def setUp(self):
        """
        テストのセットアップを行います。

        各テストメソッドが利用する基本的なチャット履歴のデータを準備します。
        """
        self.chat_history = [
            Message(content="Hello", role=RoleType.USER),
            Message(content=", ", role=RoleType.ASSISTANT),
            Message(content="world!", role=RoleType.USER),
        ]

    def test_count_tokens(self):
        """
        count_tokens関数の正確な動作を確認します。

        以下をテストします:
            1. 与えられた文字列のトークン数が正しい整数として返され、0を上回ること。
            2. 空文字列が与えられた場合、トークン数がゼロになること。
        """
        token_count = count_tokens("こんにちは、世界!")
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)

        token_count_empty = count_tokens("")
        self.assertEqual(token_count_empty, 0)

    def test_cut_down_chat_history(self):
        """
        cut_down_chat_history関数がチャット履歴を変更しない場合（削減が不要な状況）をテストします。

        - `config.max_tokens > チャット履歴すべてのトークン数` であるとき、チャット履歴が変更されないことを確認します。
        """
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=100, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history(self.chat_history, config)
        self.assertIsInstance(cut_history, list)
        self.assertEqual(len(cut_history), 3)

    def test_cut_down_chat_history_with_less_max_tokens(self):
        """
        cut_down_chat_history関数がチャット履歴を正しく削減する場合をテストします。

        - config.max_tokens を極端に小さくした場合、古いメッセージが削除され、
          必要なトークン数を満たす、最も新しいメッセージだけが残ることを確認します。
        """
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=2, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history(self.chat_history, config)
        self.assertEqual(len(cut_history), 1)
        self.assertEqual(cut_history[0].content, "world!")

    def test_cut_down_chat_history_empty(self):
        """
        cut_down_chat_history関数が空の履歴を正しく処理することをテストします。

        - チャット履歴が空の場合、関数が空のリストを返すことを確認します。
        """
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=100, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history([], config)
        self.assertEqual(cut_history, [], "空のリストであるはずです")


class TestValidateTemperature(TestCase):
    """
    validate_temperature関数をテストするためのテストケース。

    - 温度パラメータが有効な値であるかどうかを確認します。
    """

    def test_valid_temperature(self):
        """
        有効な温度値が与えられた場合、エラーが発生せず値がそのまま返却されることをテストします。

        テスト範囲:
            - 温度: 0, 0.5, 1（有効な範囲内）
        """
        for temp in [0, 0.5, 1]:
            result = validate_temperature(temp)
            self.assertEqual(result, temp)

    def test_invalid_temperature(self):
        """
        無効な温度値が与えられた場合、ValueErrorがスローされることをテストします。

        テスト範囲:
            - 温度: -1, 1.5（有効範囲外）
        """
        for temp in [-1, 1.5]:
            with self.assertRaises(ValueError):
                validate_temperature(temp)
