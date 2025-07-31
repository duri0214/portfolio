import unittest
from unittest.mock import patch

from ai_agent.domain.service.turn_management import TurnManagementService
from ai_agent.models import Entity


class TurnManagementServiceTestCase(unittest.TestCase):
    """TurnManagementServiceのテストケース

    このテストケースでは、TurnManagementServiceクラスの機能をテストします。
    TurnManagementServiceは、エンティティの行動順序や応答可能性を管理する
    サービスクラスです。

    主な機能は以下の通りです：
    1. エンティティの速度に基づいた次ターンの増分計算
    2. エンティティのthinking_typeに基づいた応答可能性の判定
    3. タイムラインの初期化と次のアクション予測

    テストでは、各機能が正しく動作することを検証します。特に、
    速度に基づく増分計算と、各種thinking_engine（GoogleMapsReview、
    CloudActPdf、DecliningBirthRatePdf）との連携による応答可能性の
    判定ロジックを重点的に確認します。
    """

    def test_calculate_next_turn_increment(self):
        """calculate_next_turn_increment メソッドのテスト

        このテストでは、エンティティの速度に基づいて次のターン増分を
        計算する機能が正しく動作することを検証します。

        テストケース：
        1. 通常の速度値（2.0, 1.0, 0.5）に対する増分計算
        2. 極端な速度値（0.1, 10.0）に対する増分計算

        速度と増分は反比例の関係にあり、速度が速いエンティティ（値が大きい）ほど
        増分が小さく、頻繁に行動できることを確認します。逆に、速度が遅い
        エンティティは増分が大きく、行動間隔が長くなります。

        計算の仕組み：
        増分 = 1 / 速度
        例：速度2.0 → 増分0.5（= 1/2）
            速度1.0 → 増分1.0（= 1/1）
            速度0.5 → 増分2.0（= 1/0.5）

        この逆数関係により、速度が2倍になると行動間隔は1/2になり、
        同じ時間内でより多くの行動が可能になります。
        """
        # テストケース1: 通常の速度値に対する増分計算
        self.assertEqual(TurnManagementService.calculate_next_turn_increment(2.0), 0.5)
        self.assertEqual(TurnManagementService.calculate_next_turn_increment(1.0), 1.0)
        self.assertEqual(TurnManagementService.calculate_next_turn_increment(0.5), 2.0)

        # テストケース2: 極端な速度値に対する増分計算
        self.assertEqual(TurnManagementService.calculate_next_turn_increment(0.1), 10.0)
        self.assertEqual(TurnManagementService.calculate_next_turn_increment(10.0), 0.1)

    @patch(
        "ai_agent.domain.service.thinking_engines.googlemaps_review.GoogleMapsReviewService.can_respond"
    )
    def test_can_respond_to_input_google_maps(self, mock_can_respond):
        """can_respond_to_input メソッドのテスト (GoogleMapsReviewService)
        このテストでは、thinking_type="google_maps_based"を持つエンティティが
        入力テキストに応答可能かどうかを判定する機能をテストします。

        テストケース：
        1. GoogleMapsReviewService.can_respondがTrueを返す場合、
           エンティティも応答可能と判定される
        2. GoogleMapsReviewService.can_respondがFalseを返す場合、
           エンティティも応答不可と判定される

        このテストではGoogleMapsReviewService.can_respondメソッドをモック化し、
        TurnManagementServiceが適切なサービスを呼び出し、その結果を正しく
        処理することを検証します。
        """
        # テストケース1: エンティティが応答可能な場合
        mock_can_respond.return_value = True
        entity = Entity(name="マップボット", thinking_type="google_maps_based")
        result = TurnManagementService.can_respond_to_input(
            entity, "レストランを探して"
        )
        self.assertTrue(result)
        mock_can_respond.assert_called_once_with("レストランを探して", entity)

        # テストケース2: エンティティが応答不可能な場合
        mock_can_respond.return_value = False
        result = TurnManagementService.can_respond_to_input(entity, "無関係な質問")
        self.assertFalse(result)

    @patch(
        "ai_agent.domain.service.thinking_engines.cloud_act_pdf.CloudActPdfService.can_respond"
    )
    def test_can_respond_to_input_cloud_act(self, mock_can_respond):
        """can_respond_to_input メソッドのテスト (CloudActPdfService)

        このテストでは、thinking_type="cloud_act_based"を持つエンティティが
        入力テキストに応答可能かどうかを判定する機能をテストします。

        テストケース：
        CloudActPdfService.can_respondがTrueを返す場合、
        エンティティも応答可能と判定される

        CloudActPdfServiceは「法律」や「クラウド」などのキーワードを含む入力に
        対して応答可能かどうかを判断します。このテストではcan_respondメソッドを
        モック化し、TurnManagementServiceが適切に結果を処理することを検証します。
        """
        # テストケース1: Cloud Act関連の質問に応答可能な場合
        mock_can_respond.return_value = True
        entity = Entity(name="法律ボット", thinking_type="cloud_act_based")
        result = TurnManagementService.can_respond_to_input(entity, "Cloud Actについて")
        self.assertTrue(result)
        mock_can_respond.assert_called_once_with("Cloud Actについて", entity)

    @patch(
        "ai_agent.domain.service.thinking_engines.declining_birth_rate_pdf.DecliningBirthRatePdfService.can_respond"
    )
    def test_can_respond_to_input_declining_birth_rate(self, mock_can_respond):
        """can_respond_to_input メソッドのテスト (DecliningBirthRatePdfService)

        このテストでは、thinking_type="declining_birth_rate_based"を持つエンティティが
        入力テキストに応答可能かどうかを判定する機能をテストします。

        テストケース：
        DecliningBirthRatePdfService.can_respondがTrueを返す場合、
        エンティティも応答可能と判定される

        DecliningBirthRatePdfServiceは「少子化」「出生率」「子育て」などの
        キーワードを含む入力に対して応答可能かどうかを判断します。
        このテストではcan_respondメソッドをモック化し、TurnManagementServiceが
        適切に結果を処理することを検証します。
        """
        # テストケース1: 少子化関連の質問に応答可能な場合
        mock_can_respond.return_value = True
        entity = Entity(name="少子化ボット", thinking_type="declining_birth_rate_based")
        result = TurnManagementService.can_respond_to_input(
            entity, "少子化対策について"
        )
        self.assertTrue(result)
        mock_can_respond.assert_called_once_with("少子化対策について", entity)

    def test_can_respond_to_input_default(self):
        """can_respond_to_input メソッドのテスト (デフォルトケース)

        このテストでは、サポートされていないthinking_typeを持つエンティティの
        応答可能性判定をテストします。

        テストケース：
        未知または未サポートのthinking_typeを持つエンティティは、
        デフォルトでTrue（応答可能）と判定される

        これは、システムが認識していない種類のエンティティに対しても
        基本的な応答能力を確保するためのフォールバック動作です。
        この動作により、新しいthinking_typeが追加された場合でも、
        システムは一貫して動作し続けることができます。
        """
        # テストケース1: 未知のthinking_typeでもデフォルトで応答可能
        entity = Entity(name="一般ボット", thinking_type="unsupported_type")
        result = TurnManagementService.can_respond_to_input(entity, "何か質問")
        self.assertTrue(result)
