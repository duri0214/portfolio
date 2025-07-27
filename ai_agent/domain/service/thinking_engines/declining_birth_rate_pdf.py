from lib.llm.valueobject.rag import PdfDataloader


class DecliningBirthRatePdfService:
    _pdf_loader = None

    @classmethod
    def _get_pdf_loader(cls):
        """シングルトンパターンでPDFローダーを取得"""
        if cls._pdf_loader is None:
            cls._pdf_loader = PdfDataloader(
                "lib/llm/pdf_sample/令和4年版少子化社会対策白書全体版（PDF版）.pdf"
            )
        return cls._pdf_loader

    @staticmethod
    def can_respond(input_text: str, entity) -> bool:
        """
        少子化対策PDFに基づいてエンティティが応答可能かどうかを判定します。

        Args:
            input_text (str): チェック対象の入力テキスト
            entity (Entity): 評価対象のエンティティ

        Returns:
            bool: 入力テキストが少子化に関連する場合はTrue
        """
        # PDFデータの内容に基づいて、このエンティティが応答すべきかを判断
        # 現時点では、特定のキーワードに基づく簡易な判定
        relevant_keywords = [
            "少子化",
            "出生率",
            "子育て",
            "育児",
            "結婚",
            "出産",
            "人口減少",
        ]
        return any(keyword in input_text for keyword in relevant_keywords)
