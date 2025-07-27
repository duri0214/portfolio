from abc import ABC
from typing import Optional

from ai_agent.models import Entity, RagMaterial


class BaseRagService(ABC):
    """RAGサービスの基底クラス

    このクラスはRagMaterialからデータを取得し、質問応答に利用するサービスの
    基本機能を提供します。

    Attributes:
        material_type (str): RagMaterialのタイプ識別子
        relevant_keywords (list[str]): 関連キーワードのリスト
    """

    material_type: str = ""
    relevant_keywords: list[str] = []

    @classmethod
    def load_source_to_rag_material(cls):
        """ソースデータを読み込んでRagMaterialに保存する

        Note:
            将来的にはデータソースからコンテンツを取得し、テキスト抽出・セグメント分割・
            ベクトル化を行い、RagMaterialテーブルに保存します。
            現在は開発・テスト目的のみに使用されています。
        """
        # TODO: 実際のデータ取得とエンベディング処理を実装
        #  1. データソースからコンテンツを取得
        #  2. テキストをセグメントに分割（必要な場合）
        #  3. 各セグメントをベクトル化
        #  4. RagMaterialテーブルに保存（ベクトルとメタデータを含む）
        # 現在はシーダーで登録されたデータを使用するため、実装は保留

    @classmethod
    def can_respond(cls, input_text: str, entity) -> bool:
        """入力テキストに基づいてエンティティが応答可能かどうかを判定する

        Args:
            input_text (str): チェック対象の入力テキスト
            entity (Entity): 評価対象のエンティティ

        Returns:
            bool: 入力テキストが関連キーワードに一致し、かつ
                 必要なデータがRagMaterialに存在する場合にTrue
        """
        # まず関連データが存在するか確認
        if not cls._check_data_exists():
            # データが存在しない場合は応答できない
            return False

        # キーワードマッチングで関連性を判定
        return cls._check_relevance(input_text)

    @classmethod
    def _check_data_exists(cls) -> bool:
        """必要なデータが存在するかを確認する

        Returns:
            bool: データが存在する場合True
        """
        if cls.material_type == "":
            return False

        return RagMaterial.objects.filter(material_type=cls.material_type).exists()

    @classmethod
    def _check_relevance(cls, input_text: str) -> bool:
        """入力テキストが関連キーワードに一致するかを確認する

        Args:
            input_text (str): チェック対象の入力テキスト

        Returns:
            bool: 関連キーワードに一致する場合True
        """
        if not cls.relevant_keywords:
            return False

        return any(
            keyword.lower() in input_text.lower() for keyword in cls.relevant_keywords
        )

    @classmethod
    def get_content(cls) -> str:
        """RagMaterialから内容を取得する

        Returns:
            str: RagMaterialから取得したコンテンツ
        """
        material = RagMaterial.objects.filter(material_type=cls.material_type).first()
        if material:
            return material.source_text
        return f"{cls.material_type}に関する情報が見つかりませんでした。"

    @classmethod
    def generate_rag_response(cls, entity: Entity, input_text: str) -> Optional[str]:
        """RAGベースのレスポンスを生成する

        入力テキストと保存されたRAG素材に基づいて、適切な応答を生成します。
        RAGベースの応答が不可能な場合はNoneを返します。

        Args:
            entity (Entity): 応答を生成するエンティティ
            input_text (str): ユーザーからの入力テキスト

        Returns:
            Optional[str]: 生成された応答、または応答できない場合はNone
        """
        if not cls.can_respond(input_text, entity):
            return None

        # 関連するコンテンツを取得
        content = cls.get_content()

        # 入力と取得したコンテンツに基づいて応答を生成
        response = (
            f"{entity.name}は{cls.material_type}に基づいて以下の情報を提供します:\n\n"
        )
        response += content

        return response
