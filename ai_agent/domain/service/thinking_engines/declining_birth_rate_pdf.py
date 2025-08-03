from ai_agent.domain.service.thinking_engines.base_rag_service import BaseRagService
from ai_agent.models import Entity
from lib.llm.valueobject.rag import PdfDataloader


class DecliningBirthRatePdfService(BaseRagService):
    """少子化対策PDFに関するRAGサービス"""

    _pdf_loader = None
    _pdf_path = "lib/llm/pdf_sample/令和4年版少子化社会対策白書全体版（PDF版）.pdf"
    material_type = "declining_birth_rate_pdf"
    relevant_keywords = [
        "少子化",
        "出生率",
        "子育て",
        "育児",
        "結婚",
        "出産",
        "人口減少",
    ]

    def __init__(self, relevant_keywords: list[str] = None):
        super().__init__(relevant_keywords)

    @classmethod
    def _get_pdf_loader(cls):
        """シングルトンパターンでPDFローダーを取得

        Note:
            現在実際のPDF解析は行われておらず、あらかじめデータベースシーダーで
            登録した少子化対策白書PDFの要約・抜粋を使用しています。このメソッドは
            将来的に実際のPDF解析を実装する際に使用される予定です。
        """
        if cls._pdf_loader is None:
            cls._pdf_loader = PdfDataloader(cls._pdf_path)
        return cls._pdf_loader

    @classmethod
    def load_source_to_rag_material(cls):
        """PDFを読み込んでRagMaterialに保存する

        Note:
            将来的にはPDFファイルを読み込み、テキスト抽出・セグメント分割・ベクトル化を行い、
            RagMaterialテーブルに保存します。現在は開発・テスト目的のみに使用されています。
        """
        # TODO: 実際のPDF読み込みとエンベディング処理を実装
        #  1. PDFファイルからテキストを抽出
        #  2. テキストをセグメントに分割
        #  3. 各セグメントをベクトル化
        #  4. RagMaterialテーブルに保存（ベクトルとメタデータを含む）
        loader = cls._get_pdf_loader()
        # 現在はシーダーで登録されたデータを使用するため、実装は保留
        # 基底クラスのメソッドを呼び出す
        super().load_source_to_rag_material()

    @classmethod
    def get_pdf_content(cls):
        """少子化対策PDFの内容を取得します。

        Note:
            現在はPDFファイルから直接抽出したテキストではなく、シーダーで事前に
            登録されたサンプルデータや要約が使用されています。実際のPDF解析と
            データ抽出機能は将来的な実装が予定されています。

        Returns:
            str: PDFから抽出したテキスト（または事前登録されたサンプルデータ）
        """
        return cls.get_contents_merged()

    @classmethod
    def generate_rag_response(cls, entity: Entity, input_text: str):
        """少子化対策に関する入力に対してRAGベースのレスポンスを生成する

        Args:
            entity (Entity): 応答を生成するエンティティ
            input_text (str): ユーザーからの入力テキスト

        Returns:
            Optional[str]: 生成された応答、または応答できない場合はNone
        """
        # 基底クラスのgenerate_rag_responseメソッドを呼び出す
        response = super().generate_rag_response(entity, input_text)

        # レスポンスをより少子化対策に特化した形式に整形
        if response:
            # 特定のキーワードに基づいて応答をカスタマイズする例
            if "出生率" in input_text:
                response += "\n\n特に出生率に関するデータは重要な指標です。"
            elif "子育て支援" in input_text:
                response += "\n\n子育て支援策は少子化対策の重要な柱の一つです。"

        return response
