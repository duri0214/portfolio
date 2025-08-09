from django.test import TestCase

from ai_agent.domain.factories.rag_metadata_factory import RagMetadataFactory
from ai_agent.domain.valueobject.context_analyzer import (
    PdfSourceMetadata,
    GoogleMapsMetadata,
)


class TestRagMetadataFactory(TestCase):
    """
    RAGメタデータファクトリのテストケース

    このテストクラスでは、異なる種類のメタデータを適切なVOに変換する
    ファクトリクラスの機能をテストします。主な検証項目：
    - material_typeに応じた適切なVOの生成
    - 辞書データからVOへの正確な変換
    - 未対応のmaterial_typeに対するエラー処理

    シナリオ：
    RAG素材はmaterial_typeによって異なる種類のメタデータを持ちます。
    ファクトリパターンを使用して、正しい型のVOを生成することで、
    型安全なメタデータ処理を実現します。
    """

    def test_create_google_maps_metadata(self):
        """
        Google Mapsメタデータの作成をテスト

        このテストでは、GoogleMapsメタデータの辞書からVOへの変換が
        ファクトリを通じて正しく行われることを確認します。
        """
        # シーダーデータと同じ順序でメタデータ辞書を作成
        metadata_dict = {
            "rating": 4.7,
            "latitude": 35.658584,
            "longitude": 139.745438,
            "author_name": "佐藤花子",
            "review_date": "2023-11-20T16:45:00",
            "location_name": "東京タワー",
        }

        metadata = RagMetadataFactory.create("google_maps_based", metadata_dict)

        # 正しい型のVOが生成されたか確認
        self.assertIsInstance(metadata, GoogleMapsMetadata)

        # VOの内容が正しいか確認
        self.assertEqual(metadata.location_name, "東京タワー")
        self.assertEqual(metadata.rating, 4.7)
        self.assertEqual(metadata.latitude, 35.658584)
        self.assertEqual(metadata.longitude, 139.745438)

    def test_create_pdf_metadata(self):
        """
        PDFメタデータの作成をテスト

        このテストでは、PDFメタデータの辞書からVOへの変換が
        ファクトリを通じて正しく行われることを確認します。
        Cloud ActとDeclines Birth Rate両方のPDFに対して
        同じPdfSourceMetadataクラスが使用されることを検証します。

        注意：
        現在はfile_pathのみを持つシンプルな実装ですが、
        将来的に拡張される可能性があります。
        """
        # 実際のシーダーデータと同様のデータ
        metadata_dict = {
            "file_path": "lib/llm/pdf_sample/doj_cloud_act_white_paper_2019_04_10.pdf"
        }

        # Cloud Act PDFの場合
        cloud_act_metadata = RagMetadataFactory.create("cloud_act_based", metadata_dict)
        self.assertIsInstance(cloud_act_metadata, PdfSourceMetadata)
        self.assertEqual(
            cloud_act_metadata.file_path,
            "lib/llm/pdf_sample/doj_cloud_act_white_paper_2019_04_10.pdf",
        )

        # 少子化対策PDFの場合も同じPdfSourceMetadataクラスが使用される
        birth_rate_metadata = RagMetadataFactory.create(
            "declining_birth_rate_based", metadata_dict
        )
        self.assertIsInstance(birth_rate_metadata, PdfSourceMetadata)
        self.assertEqual(
            birth_rate_metadata.file_path,
            "lib/llm/pdf_sample/doj_cloud_act_white_paper_2019_04_10.pdf",
        )

    def test_unsupported_material_type(self):
        """
        未対応のmaterial_typeでエラー発生をテスト

        このテストでは、未登録のmaterial_typeが指定された場合に
        適切なエラーが発生することを確認します。

        これは、未知のデータ型に対する安全な対応を保証するために重要です。
        """
        with self.assertRaises(ValueError) as context:
            RagMetadataFactory.create("unknown_type", {})

        # エラーメッセージも確認
        self.assertIn("Unsupported material_type", str(context.exception))
