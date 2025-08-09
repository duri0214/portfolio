from django.test import TestCase

from lib.llm.service.completion import cut_down_chat_history
from lib.llm.valueobject.completion import RoleType, Message


class TestLlmService(TestCase):
    """
    LLMサービス関連の関数をテストするためのテストケース。

    対象とする関数:
        - cut_down_chat_history: チャット履歴をメッセージ件数制限に基づいて削減する関数。
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

    def test_cut_down_chat_history(self):
        """
        cut_down_chat_history関数がチャット履歴を変更しない場合（削減が不要な状況）をテストします。

        - チャット履歴のメッセージ数が max_messages 以下のとき、チャット履歴が変更されないことを確認します。
        """
        cut_history = cut_down_chat_history(self.chat_history)
        self.assertIsInstance(cut_history, list)
        self.assertEqual(len(cut_history), 3)

    def test_cut_down_chat_history_with_less_max_messages(self):
        """
        cut_down_chat_history関数がチャット履歴を正しく削減する場合をテストします。

        - max_messages を小さくした場合、古いメッセージが削除され、
          最新の指定件数のメッセージだけが残ることを確認します。
        """
        cut_history = cut_down_chat_history(self.chat_history, max_messages=1)
        self.assertEqual(len(cut_history), 1)
        self.assertEqual(cut_history[0].content, "world!")

    def test_cut_down_chat_history_empty(self):
        """
        cut_down_chat_history関数が空の履歴を正しく処理することをテストします。

        - チャット履歴が空の場合、関数が空のリストを返すことを確認します。
        """
        cut_history = cut_down_chat_history([])
        self.assertEqual(cut_history, [], "空のリストであるはずです")
