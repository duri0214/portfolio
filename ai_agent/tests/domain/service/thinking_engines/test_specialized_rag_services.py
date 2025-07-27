import unittest
from unittest.mock import patch

from ai_agent.domain.service.thinking_engines.cloud_act_pdf import CloudActPdfService
from ai_agent.domain.service.thinking_engines.declining_birth_rate_pdf import (
    DecliningBirthRatePdfService,
)
from ai_agent.domain.service.thinking_engines.googlemaps_review import (
    GoogleMapsReviewService,
)
from ai_agent.models import Entity


class CloudActPdfServiceTestCase(unittest.TestCase):
    """CloudActPdfServiceのテストケース

    このテストケースでは、CloudActPdfServiceクラスの機能をテストします。
    CloudActPdfServiceは、米国のCloud Act法律文書から情報を抽出し、
    関連するキーワードを含む質問に対して特化した応答を生成するサービスです。

    BaseRagServiceを継承し、特に「法律」や「クラウド」に関連するキーワードを
    含む入力に対して、追加情報を提供するように拡張されています。

    テストでは、基底クラスのgenerate_rag_responseメソッドをモック化し、
    CloudActPdfServiceの拡張機能が正しく動作することを検証します。
    """

    @patch(
        "ai_agent.domain.service.thinking_engines.base_rag_service.BaseRagService.generate_rag_response"
    )
    def test_generate_rag_response(self, mock_base_generate):
        """generate_rag_response メソッドのテスト

        このテストでは、CloudActPdfServiceのgenerate_rag_responseメソッドが
        入力テキストに含まれるキーワードに基づいて適切に応答を拡張することを検証します。

        テスト内容：
        1. 「法律」というキーワードを含む入力に対する応答の拡張
        2. 「クラウド」というキーワードを含む入力に対する応答の拡張

        基底クラスのgenerate_rag_responseメソッドはモック化し、このテストでは
        CloudActPdfServiceによる応答の拡張部分のみに焦点を当てています。
        """
        # モックの設定 - 基底クラスの応答
        mock_base_generate.return_value = "基本的な応答"

        # テストケース1: 「法律」キーワードに対する応答拡張
        entity = Entity(name="法律ボット")
        result = CloudActPdfService.generate_rag_response(entity, "法律について教えて")
        self.assertIn("基本的な応答", result)
        self.assertIn("Cloud Actは米国の法律", result)

        # テストケース2: 「クラウド」キーワードに対する応答拡張
        result = CloudActPdfService.generate_rag_response(
            entity, "クラウドサービスについて教えて"
        )
        self.assertIn("基本的な応答", result)
        self.assertIn("クラウドサービスを利用する企業", result)


class DecliningBirthRatePdfServiceTestCase(unittest.TestCase):
    """DecliningBirthRatePdfServiceのテストケース

    このテストケースでは、DecliningBirthRatePdfServiceクラスの機能をテストします。
    DecliningBirthRatePdfServiceは、少子化対策や人口動態に関する文書から
    情報を抽出し、関連する質問に対して特化した応答を生成するサービスです。

    BaseRagServiceを継承し、特に「出生率」や「子育て支援」などのキーワードを
    含む入力に対して、より詳細な情報や分析を提供するように拡張されています。

    テストでは、基底クラスのgenerate_rag_responseメソッドをモック化し、
    特定のキーワードに応じた応答拡張機能が正しく動作することを検証します。
    """

    @patch(
        "ai_agent.domain.service.thinking_engines.base_rag_service.BaseRagService.generate_rag_response"
    )
    def test_generate_rag_response(self, mock_base_generate):
        """generate_rag_response メソッドのテスト

        このテストでは、DecliningBirthRatePdfServiceのgenerate_rag_responseメソッドが
        入力テキストに含まれるキーワードに基づいて適切に応答を拡張することを検証します。

        テスト内容：
        1. 「出生率」というキーワードを含む入力に対する応答の拡張
        2. 「子育て支援」というキーワードを含む入力に対する応答の拡張

        基底クラスのgenerate_rag_responseメソッドはモック化し、このテストでは
        DecliningBirthRatePdfServiceによる応答の拡張部分のみに焦点を当てています。
        """
        # モックの設定 - 基底クラスの応答
        mock_base_generate.return_value = "基本的な応答"

        # テストケース1: 「出生率」キーワードに対する応答拡張
        entity = Entity(name="少子化ボット")
        result = DecliningBirthRatePdfService.generate_rag_response(
            entity, "出生率について教えて"
        )
        self.assertIn("基本的な応答", result)
        self.assertIn("出生率に関するデータは重要な指標", result)

        # テストケース2: 「子育て支援」キーワードに対する応答拡張
        result = DecliningBirthRatePdfService.generate_rag_response(
            entity, "子育て支援について教えて"
        )
        self.assertIn("基本的な応答", result)
        self.assertIn("子育て支援策は少子化対策の重要な柱", result)


class GoogleMapsReviewServiceTestCase(unittest.TestCase):
    """GoogleMapsReviewServiceのテストケース

    このテストケースでは、GoogleMapsReviewServiceクラスの機能をテストします。
    GoogleMapsReviewServiceは、Googleマップから取得した場所のレビューデータを
    活用し、特定の場所やカテゴリに関する質問に対して、実際のユーザーレビューを
    基にした応答を生成するサービスです。

    BaseRagServiceを継承し、レストランやカフェなどの場所に関する質問に対して、
    レビューデータから抽出した情報を提供します。また、can_respondメソッドにより
    応答可能かどうかを判断する機能も備えています。

    テストでは、get_reviewsメソッドとcan_respondメソッドをモック化し、
    様々な入力に対する応答生成機能が正しく動作することを検証します。また、
    応答できない場合に適切にNoneを返すことも確認します。
    """

    @patch(
        "ai_agent.domain.service.thinking_engines.googlemaps_review.GoogleMapsReviewService.can_respond"
    )
    @patch(
        "ai_agent.domain.service.thinking_engines.googlemaps_review.GoogleMapsReviewService.get_reviews"
    )
    def test_generate_rag_response(self, mock_get_reviews, mock_can_respond):
        """generate_rag_response メソッドのテスト

        このテストでは、GoogleMapsReviewServiceのgenerate_rag_responseメソッドが
        以下の機能を正しく実行することを検証します：

        1. レストランに関する質問に対して、レビューデータを含む応答を生成
        2. カフェに関する質問に対して、レビューデータを含む応答を生成
        3. 応答できない質問（can_respondがFalseを返す場合）に対してNoneを返す

        GoogleMapsReviewServiceのcan_respondメソッドとget_reviewsメソッドは
        モック化されており、テストの制御性と再現性を高めています。
        """
        # モックの設定 - レビューデータとレスポンス可否
        mock_can_respond.return_value = True
        mock_get_reviews.return_value = "レビュー1\n\nレビュー2"

        # テストケース1: 「レストラン」キーワードに対する応答生成
        entity = Entity(name="レビューボット")
        result = GoogleMapsReviewService.generate_rag_response(
            entity, "おすすめのレストランは？"
        )
        self.assertIn("レビューボット", result)
        self.assertIn("レビュー1", result)
        self.assertIn("レビュー2", result)
        self.assertIn("おすすめのレストランを選ぶ際", result)

        # テストケース2: 「カフェ」キーワードに対する応答生成
        result = GoogleMapsReviewService.generate_rag_response(
            entity, "おすすめのカフェは？"
        )
        self.assertIn("レビューボット", result)
        self.assertIn("レビュー1", result)
        self.assertIn("レビュー2", result)
        self.assertIn("カフェでの作業環境", result)

        # テストケース3: 応答できない場合のテスト
        mock_can_respond.return_value = False
        result = GoogleMapsReviewService.generate_rag_response(entity, "無関係な質問")
        self.assertIsNone(result)
