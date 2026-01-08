import unittest
from unittest.mock import MagicMock, patch


from lib.llm.service.semantic_guard import (
    SemanticGuardService,
    SemanticGuardServiceWrapper,
)
from lib.llm.valueobject.semantic_guard import GuardRailSignal, SemanticGuardException


class TestSemanticGuardService(unittest.TestCase):
    """
    SemanticGuardService の意味差分検索パイプラインを検証するテストスイート。

    信号機モデル（GREEN, YELLOW, RED）に基づいたガードレールの挙動を、
    以下のシナリオに沿ってテストします：
    1. GREEN: RAG にヒットした場合（社内ナレッジに基づく安全な回答）
    2. YELLOW: RAG 未ヒットだが、LLM の回答に禁止ワードが含まれない場合
    3. RED: LLM の回答に禁止ワードが意味的に含まれる場合（例外発生）
    """

    @patch("lib.llm.service.semantic_guard.chromadb.PersistentClient")
    @patch("lib.llm.service.semantic_guard.OpenAIEmbeddingFunction")
    def setUp(self, mock_ef, mock_chroma):
        """
        テスト環境のセットアップ。
        ChromaDB クライアントと埋め込み関数をモック化し、
        禁止ワード用と RAG 用のコレクションを切り分けて返却するように設定します。
        """
        self.mock_chroma_client = mock_chroma.return_value
        self.mock_ef = mock_ef.return_value

        # コレクションのモック
        self.mock_forbidden_collection = MagicMock()
        self.mock_rag_collection = MagicMock()

        def side_effect(name, **_):
            if name == "forbidden_words":
                return self.mock_forbidden_collection
            return self.mock_rag_collection

        self.mock_chroma_client.get_or_create_collection.side_effect = side_effect

        self.service = SemanticGuardService(api_key="fake-key")

    def test_evaluate_green_on_rag_hit(self):
        """
        シナリオ: RAG ヒット（🟢 GREEN）
        - ユーザー入力が RAG コレクション内の既存ドキュメントにヒットした場合
        - 一般 LLM を呼び出すことなく、GREEN 信号が返ることを確認します。
        """
        # RAGヒットする状況をシミュレート
        self.mock_rag_collection.query.return_value = {"documents": [["some context"]]}

        result = self.service.evaluate("こんにちは")

        self.assertEqual(result.signal, GuardRailSignal.GREEN)
        self.assertEqual(result.reason, "RAG_HIT")

    def test_evaluate_yellow_on_rag_miss(self):
        """
        シナリオ: RAG 未ヒットかつ安全な回答（🟡 YELLOW）
        - ユーザー入力が RAG にヒットしない場合
        - 一般 LLM の回答が生成され、その内容に禁止ワードが含まれない場合
        - YELLOW 信号が返り、正常に終了することを確認します。
        """
        # RAGヒットしない状況をシミュレート
        self.mock_rag_collection.query.return_value = {"documents": [[]]}

        # ワードチェックもパスする状況（距離が閾値 0.35 以上）
        self.mock_forbidden_collection.query.return_value = {
            "distances": [[0.8]],  # 閾値より大きい＝似ていない
            "documents": [["競合他社"]],
        }

        def mock_llm_response(_):
            return "安全な回答です"

        result = self.service.evaluate("質問", llm_response_provider=mock_llm_response)

        self.assertEqual(result.signal, GuardRailSignal.YELLOW)
        self.assertEqual(result.reason, "RAG_MISS")

    def test_evaluate_red_on_forbidden_word(self):
        """
        シナリオ: 禁止ワードの検知（🔴 RED）
        - ユーザー入力が RAG にヒットせず、一般 LLM の回答が生成された場合
        - 生成された回答に、禁止ワード（例: 佐川急便）が意味的に含まれる場合
        - SemanticGuardException が発生し、RED 信号が返ることを確認します。
        """
        # RAGヒットしない状況
        self.mock_rag_collection.query.return_value = {"documents": [[]]}

        # ワードチェックでヒットする状況（距離が閾値 0.35 未満）
        self.mock_forbidden_collection.query.return_value = {
            "distances": [[0.1]],  # 閾値より小さい＝極めて近い
            "documents": [["佐川急便"]],
        }

        def mock_llm_response(_):
            return "佐川急便で送ります"

        with self.assertRaises(SemanticGuardException) as cm:
            self.service.evaluate("質問", llm_response_provider=mock_llm_response)

        self.assertEqual(cm.exception.result.signal, GuardRailSignal.RED)
        self.assertEqual(cm.exception.result.reason, "FORBIDDEN_WORD_DETECTED")

    def test_wrapper_guardrail_blocks_forbidden_word(self):
        """
        シナリオ: ラッパー経由でのワードブロック
        - SemanticGuardServiceWrapper を使用してガードレール関数を作成
        - 禁止ワードが含まれるテキストを渡した場合に、期待通り blocked: True が返ることを確認します。
        """
        # ワードチェックでヒットする状況
        self.mock_forbidden_collection.query.return_value = {
            "distances": [[0.1]],
            "documents": [["佐川急便"]],
        }

        wrapper = SemanticGuardServiceWrapper(self.service)
        guardrail = wrapper.create_guardrail()

        # 引数は (context, agent, text)
        result = guardrail(None, None, "佐川急便で配送します")

        self.assertTrue(result["blocked"])
        self.assertIn("禁止ワード", result["message"])

    def test_wrapper_guardrail_allows_safe_text(self):
        """
        シナリオ: ラッパー経由での安全なテキスト許可
        - セーフなテキストを渡した場合に、blocked: False が返ることを確認します。
        """
        # ワードチェックでヒットしない状況
        self.mock_forbidden_collection.query.return_value = {
            "distances": [[0.8]],
            "documents": [["競合他社"]],
        }

        wrapper = SemanticGuardServiceWrapper(self.service)
        guardrail = wrapper.create_guardrail()

        result = guardrail(None, None, "安全なメッセージ")

        self.assertFalse(result["blocked"])


if __name__ == "__main__":
    unittest.main()
