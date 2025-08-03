from ai_agent.domain.service.thinking_engines.base_rag_service import BaseRagService
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
