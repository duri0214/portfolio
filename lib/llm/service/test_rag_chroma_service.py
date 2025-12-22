import unittest
from unittest.mock import MagicMock, patch
import tempfile
import os
import shutil
from lib.llm.service.completion import OpenAILlmRagService

class TestOpenAILlmRagService(unittest.TestCase):
    """
    OpenAILlmRagService の挙動を検証するためのテストスイート。

    【テストの背景とシナリオ】
    このテストは、Chroma を使った RAG（検索拡張生成）基盤が正しく機能しているかを保証するために作成されました。
    将来、OpenAI の API 仕様が変わったり、Chroma のバージョンを上げたりした際に、
    「検索ロジックが壊れていないか」「メタデータフィルタが正しく効いているか」を即座に確認できます。

    ■ シナリオ: 「文学作品検索システムの保守」
    あなたは今、過去の文学作品（ドキュメント）を Vector DB に蓄積し、
    特定の著者の作品だけを絞り込んで回答させる機能をメンテナンスしています。
    1. まず、一時的なディレクトリにDBを作成し、人物1（例：太宰）と人物2（例：漱石）の「作品の一節」を登録します（Upsert）。
    2. 次に、「太宰治」というフィルタをかけて質問を投げます。
    3. 期待値として、検索結果に漱石が混じらず、人物1の作品に基づいた回答が生成されることを確認します。
    4. 最後に、DBを一旦クローズして再起動しても、データが消えずに残っているか（永続化）を検証します。
    """

    def setUp(self):
        # 一時ディレクトリを作成して Chroma のパスにする
        self.test_dir = tempfile.mkdtemp()
        self.api_key = "sk-dummy-key"
        self.model = "gpt-4o-mini"
        
        # OpenAI API のモック
        self.patcher_openai = patch("lib.llm.service.completion.OpenAI")
        self.mock_openai_class = self.patcher_openai.start()
        self.mock_client = self.mock_openai_class.return_value
        
        # 埋め込みベクトルのダミー（3次元）
        # 人物1用: [1.0, 0.0, 0.0], 人物2用: [0.0, 1.0, 0.0], 質問用: [0.9, 0.1, 0.0]
        self.person1_vec = [1.0, 0.0, 0.0]
        self.person2_vec = [0.0, 1.0, 0.0]
        self.query_vec = [0.9, 0.1, 0.0]

        # Embeddings API のレスポンスをモック
        # テストデータのテキスト内容に応じて、事前に定義したダミーの埋め込みベクトルを返します。
        # - 「太宰」や「メロス」を含む場合: person1_vec ([1,0,0])
        # - 「漱石」や「猫」を含む場合: person2_vec ([0,1,0])
        # - それ以外（質問など）: query_vec ([0.9, 0.1, 0])
        # これにより、ベクトル検索のシミュレーションにおいて、期待通りの類似度（内積）が得られるようにしています。
        def side_effect_embed(**kwargs):
            input_texts = kwargs.get("input") or []
            mock_resp = MagicMock()
            data = []
            for text in input_texts:
                d = MagicMock()
                if "太宰" in text or "メロス" in text:
                    d.embedding = self.person1_vec
                elif "漱石" in text or "猫" in text:
                    d.embedding = self.person2_vec
                else:
                    d.embedding = self.query_vec
                data.append(d)
            mock_resp.data = data
            return mock_resp

        self.mock_client.embeddings.create.side_effect = side_effect_embed

        # Chat Completions API のレスポンスをモック
        self.mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="太宰治はメロスについて言及しています。"))]
        )

    def tearDown(self):
        self.patcher_openai.stop()
        # Windows で Chroma のファイルロックが解除されるのを待つか、エラーを無視する
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except PermissionError:
                pass

    def test_rag_flow_with_metadata_filter(self):
        """
        ドキュメント登録 -> フィルタ付き検索 -> 回答生成 の一連の流れをテスト。
        """
        service = OpenAILlmRagService(
            model=self.model,
            api_key=self.api_key,
            persist_directory=self.test_dir
        )

        # 1. ドキュメントの登録 (Upsert)
        docs = [
            type("Doc", (), {"page_content": "メロスは激怒した。", "metadata": {"author": "太宰治", "id": "d1"}}),
            type("Doc", (), {"page_content": "吾輩は猫である。", "metadata": {"author": "夏目漱石", "id": "s1"}})
        ]
        service.upsert_documents(docs)

        # 2. 検索と回答取得（フィルタあり）
        # 太宰治のみを対象にする
        result = service.retrieve_answer("メロスについて教えて", where_filter={"author": "太宰治"})

        # 3. 検証
        # 検索結果（source_documents）に漱石が含まれていないこと
        source_authors = [doc.metadata.get("author") for doc in result["source_documents"]]
        self.assertIn("太宰治", source_authors)
        self.assertNotIn("夏目漱石", source_authors)
        
        # 回答が返ってきていること
        self.assertEqual(result["answer"], "太宰治はメロスについて言及しています。")
        self.assertIn("太宰治", result["sources"])

    def test_persistence(self):
        """
        インスタンスを再生成してもデータが保持されていることをテスト。
        """
        # 初代サービスで書き込み
        service1 = OpenAILlmRagService(
            model=self.model,
            api_key=self.api_key,
            persist_directory=self.test_dir
        )
        service1.upsert_documents([
            type("Doc", (), {"page_content": "永続化テスト用", "metadata": {"id": "p1", "tag": "test"}})
        ])
        
        # 二代目サービスを同じディレクトリで起動
        service2 = OpenAILlmRagService(
            model=self.model,
            api_key=self.api_key,
            persist_directory=self.test_dir
        )
        
        # 既に1件データが入っているはず
        self.assertEqual(service2._collection.count(), 1)
        
        # 検索できること
        result = service2.retrieve_answer("テスト用")
        self.assertEqual(len(result["source_documents"]), 1)
        self.assertEqual(result["source_documents"][0].page_content, "永続化テスト用")

if __name__ == "__main__":
    unittest.main()
