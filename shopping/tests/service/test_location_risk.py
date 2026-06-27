from django.test import SimpleTestCase

from shopping.domain.service.location_risk import LocationRiskService


class LocationRiskServiceTest(SimpleTestCase):
    def test_assess_returns_expected_visitors_by_entry_rate(self):
        """
        シナリオ:
        - 入力: 1時間あたり30人の店前通行量。
        - 処理: 立地リスク評価サービスで期待来店数を算出する。
        - 期待値: 入店率0.5%、1.0%、2.0%に対する期待来店数が返されること。
        """
        assessment = LocationRiskService.assess(pedestrian_count_per_hour=30)

        self.assertEqual("通りすがり依存は厳しい", assessment.risk_label)
        self.assertEqual(
            [0.15, 0.3, 0.6],
            [estimate.visitors_per_hour for estimate in assessment.estimates],
        )

    def test_assess_recommends_storefront_actions_when_walkers_are_enough(self):
        """
        シナリオ:
        - 入力: 1時間あたり200人の店前通行量。
        - 処理: 立地リスク評価サービスで期待来店数を算出する。
        - 期待値: 店前施策の検証余地がある判定になること。
        """
        assessment = LocationRiskService.assess(pedestrian_count_per_hour=200)

        self.assertEqual("店前施策の検証余地あり", assessment.risk_label)
