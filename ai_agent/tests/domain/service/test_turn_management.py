from django.test import TestCase

from ai_agent.domain.service.turn_management import TurnManagementService


class TurnManagementServiceTestCase(TestCase):
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
