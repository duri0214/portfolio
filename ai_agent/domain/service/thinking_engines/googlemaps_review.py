from ai_agent.models import RagMaterial


class GoogleMapsReviewService:

    @classmethod
    def load_reviews_to_rag_material(cls):
        """Google Mapsレビューをデータソースから収集し、RagMaterialに保存します。

        Note:
            将来的にはGoogle Maps APIやスクレイピングツールを使用して
            レビューデータを取得し、ベクトル化してRagMaterialテーブルに保存します。
            現在は開発・テスト目的のみに使用されています。
        """
        # TODO: 実際のデータ収集とエンベディング処理を実装
        #  1. Google Maps APIやスクレイピングでレビューを収集
        #  2. レビューをテーマ別やカテゴリ別に整理
        #  3. 各レビューをベクトル化
        #  4. RagMaterialテーブルに保存（ベクトルとメタデータを含む）
        # 現在はシーダーで登録されたデータを使用するため、実装は保留

    @staticmethod
    def can_respond(input_text: str, entity) -> bool:
        """
        Determines if the entity can respond based on Google Maps reviews.

        TODO: Implement proper review-based logic.

        Args:
            input_text (str): The input text to evaluate.
            entity (Entity): The entity performing the evaluation.

        Returns:
            bool: Always True for now (temporarily hardcoded for testing purposes).
        """
        return True
