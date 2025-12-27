import unittest
from unittest.mock import MagicMock, patch
from lib.llm.service.completion import OpenAILlmRagService


class TestOpenAILlmRagService(unittest.TestCase):
    """
    OpenAILlmRagService の挙動を検証するためのテストスイート。
    """

    def setUp(self):
        self.api_key = "sk-dummy-key"
        self.model = "gpt-4o-mini"

        # OpenAI API のモック
        self.patcher_openai = patch("lib.llm.service.completion.OpenAI")
        self.mock_openai_class = self.patcher_openai.start()
        self.mock_client = self.mock_openai_class.return_value

        # ChromaDB のモック
        self.patcher_chroma = patch(
            "lib.llm.service.completion.chromadb.PersistentClient"
        )
        self.mock_chroma_client_class = self.patcher_chroma.start()
        self.mock_db_client = self.mock_chroma_client_class.return_value
        self.mock_collection = MagicMock()
        self.mock_db_client.get_or_create_collection.return_value = self.mock_collection

        # OpenAIEmbeddingFunction のモック
        self.patcher_ef = patch("lib.llm.service.completion.OpenAIEmbeddingFunction")
        self.mock_ef_class = self.patcher_ef.start()

        # Chat Completions API のレスポンスをモック
        self.mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="太宰治はメロスについて言及しています。")
                )
            ]
        )

    def tearDown(self):
        self.patcher_openai.stop()
        self.patcher_chroma.stop()
        self.patcher_ef.stop()

    def test_rag_flow_with_metadata_filter(self):
        """
        ドキュメント登録 -> フィルタ付き検索 -> 回答生成 の一連の流れをテスト。
        """
        service = OpenAILlmRagService(
            model=self.model, api_key=self.api_key, persist_directory="dummy_path"
        )

        # 1. ドキュメントの登録 (Upsert)
        docs = [
            type(
                "Doc",
                (),
                {
                    "page_content": "メロスは激怒した。",
                    "metadata": {"author": "太宰治", "id": "d1"},
                },
            ),
            type(
                "Doc",
                (),
                {
                    "page_content": "吾輩は猫である。",
                    "metadata": {"author": "夏目漱石", "id": "s1"},
                },
            ),
        ]
        service.upsert_documents(docs)

        # upsert が呼ばれたことを確認
        self.assertTrue(self.mock_collection.upsert.called)

        # 2. 検索と回答取得（フィルタあり）
        # 検索結果のモック設定
        self.mock_collection.query.return_value = {
            "documents": [["メロスは激怒した。"]],
            "metadatas": [[{"author": "太宰治", "id": "d1"}]],
            "ids": [["d1"]],
        }

        result = service.retrieve_answer(
            "メロスについて教えて", where_filter={"author": "太宰治"}
        )

        # 3. 検証
        # query が正しい引数で呼ばれたか
        self.mock_collection.query.assert_called_with(
            query_texts=["メロスについて教えて"],
            n_results=3,
            where={"author": "太宰治"},
        )

        # 検索結果（source_documents）に期待したデータが含まれていること
        source_authors = [
            doc.metadata.get("author") for doc in result["source_documents"]
        ]
        self.assertIn("太宰治", source_authors)
        self.assertNotIn("夏目漱石", source_authors)

        # 回答が返ってきていること
        self.assertEqual(result["answer"], "太宰治はメロスについて言及しています。")
        self.assertIn("太宰治", result["sources"])

    def test_persistence_logic(self):
        """
        初期化時に正しいパスで Client が作成されることをテスト。
        (モック化しているため、実際の永続化は Client の呼び出し引数で検証する)
        """
        test_path = "custom_chroma_path"
        service = OpenAILlmRagService(
            model=self.model, api_key=self.api_key, persist_directory=test_path
        )

        # chromadb.PersistentClient が正しいパスで呼ばれたか
        # Note: OpenAILlmRagService 内部で絶対パスに変換される可能性があるため、部分一致などで検証
        args, kwargs = self.mock_chroma_client_class.call_args
        self.assertIn(test_path, kwargs["path"])


if __name__ == "__main__":
    unittest.main()
