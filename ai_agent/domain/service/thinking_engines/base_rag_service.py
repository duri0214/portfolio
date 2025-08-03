from abc import ABC

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

    def can_respond(self, input_text: str, entity) -> bool:
        """入力テキストに基づいて応答可能かどうかを判定する

        Args:
            input_text (str): チェック対象の入力テキスト
            entity (Entity): 評価対象のエンティティ（互換性のために残す）

        Returns:
            bool: 入力テキストが関連キーワードに一致し、かつ
                 必要なデータがRagMaterialに存在する場合にTrue
        """
        # まず関連データが存在するか確認
        if not self._check_data_exists():
            # データが存在しない場合は応答できない
            return False

        # キーワードマッチングで関連性を判定
        return self._check_relevance(input_text)

    def _check_data_exists(self) -> bool:
        """必要なデータが存在するかを確認する

        material_typeが設定されていない場合、または指定されたタイプの
        RagMaterialデータが存在しない場合はFalseを返します。

        Note:
            material_typeは子クラスで必ず設定する必要があります。未設定の場合は
            不正な状態となり、RAG処理が正しく機能しません。

        Returns:
            bool: データが存在する場合True、そうでない場合はFalse
        """
        return (
            self.__class__.material_type != ""
            and RagMaterial.objects.filter(material_type=self.__class__.material_type).exists()
        )

    def _check_relevance(self, input_text: str) -> bool:
        """入力テキストが関連キーワードを含むかを確認する

        Args:
            input_text (str): チェック対象の入力テキスト

        Note:
            relevant_keywordsは子クラスで必ず設定する必要があります。未設定の場合は
            どのような入力に対しても不一致となり、RAG処理が正しく機能しません。

            このメソッドは「部分一致」で判定します。つまり、input_textの中に
            relevant_keywordsのいずれかの文字列が含まれていれば一致と判定します。

            大文字小文字は区別されません。例えば：
            - relevant_keywords=["Cat", "Dog"] のとき
            - 「私はCAT（猫）が好きです」は一致します
            - 「cat好き」も一致します

        Returns:
            bool: 入力テキストが関連キーワードのいずれかを含む場合True、含まない場合False
        """
        if not self.relevant_keywords:
            return False

        # 入力テキストを小文字に変換
        lowercase_input = input_text.lower()

        # キーワードも事前に小文字に変換してリスト化
        lowercase_keywords = [keyword.lower() for keyword in self.relevant_keywords]

        # 各キーワードが入力テキストに含まれているかチェック（部分一致）
        for keyword in lowercase_keywords:
            if keyword in lowercase_input:
                return True

        return False

    @classmethod
    def get_contents_merged(cls, separator="\n\n") -> str:
        """RagMaterialから全てのレコードを取得して結合したテキストを返す

        Args:
            separator (str, optional): 複数レコードを結合する際の区切り文字。デフォルトは改行2つ。

        Note:
            複数のRagMaterialレコードが存在する場合、全てのレコードを取得して
            指定されたセパレータで結合したテキストを返します。
            単一レコードの場合も同様に動作します。

        Returns:
            str: RagMaterialから取得した全レコードを結合したコンテンツ
        """
        materials = RagMaterial.objects.filter(material_type=cls.material_type)
        if not materials.exists():
            return f"{cls.material_type}に関する情報が見つかりませんでした。"

        # 1レコードの場合はそのまま返す
        if materials.count() == 1:
            return materials.first().source_text

        # 複数レコードの場合は結合して返す
        return separator.join([material.source_text for material in materials])

    @classmethod
    def generate_rag_response(cls, entity: Entity, input_text: str) -> str | None:
        """RAGベースのレスポンスを生成する

        入力テキストと保存されたRAG素材に基づいて、適切な応答を生成します。
        entityの応答が不可能な場合はNoneを返します。

        Note:
            現実装は真のRAG（Retrieval-Augmented Generation）ではなく、シンプルな
            キーワードマッチングに基づくコンテンツ取得と応答生成を行っています。
            - ベクトル検索を使用していない
            - セマンティック類似性での検索ではなく、キーワード部分一致
            - LLMを使用したコンテンツの再生成を行わない

            将来的な実装では以下が計画されています：
            - LangChainなどのRAGフレームワークの活用
            - 埋め込みベクトルを使用したセマンティック検索
            - 複数ソースからの情報の統合と要約
            - プロンプトエンジニアリングによる高度な応答生成

            子クラス（GoogleMapsReviewService、CloudActPdfServiceなど）では、
            material_typeとrelevant_keywordsを適切に設定し、必要に応じて
            このメソッドをオーバーライドして特定のキーワードに基づいた
            カスタム応答を生成しています。

        Args:
            entity (Entity): 応答を生成するエンティティ
            input_text (str): ユーザーからの入力テキスト

        Returns:
            str | None: 生成された応答、または応答できない場合はNone
        """
        if not cls.can_respond(input_text, entity):
            return None

        # 関連するコンテンツを取得
        content = cls.get_contents_merged()

        # 入力と取得したコンテンツに基づいて応答を生成
        response = (
            f"{entity.name}は{cls.material_type}に基づいて以下の情報を提供します:\n\n"
        )
        response += content

        return response
