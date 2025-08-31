from django.test import TestCase

from welfare_services.domain.repository.review_repository import ReviewRepository
from welfare_services.models import Facility, FacilityReview


class ReviewRepositoryTestCase(TestCase):
    """ReviewRepositoryのテストケース

    レビューリポジトリの機能を検証するテストケース群。
    主に以下の機能をテスト：
    - レビュー取得機能（承認済み/未承認/全て）
    - レビュー統計情報の計算（平均評価、分布）
    - 評価分布の集計と変換
    - エッジケース（レビューなし）の処理
    """

    def setUp(self):
        # テスト用の施設を作成
        self.facility = Facility.objects.create(
            name="テスト施設",
            address="東京都新宿区",
        )

        # テスト用のレビューデータを作成
        # 5★：3件、4★：2件、3★：1件、2★：2件、1★：1件
        ratings_data = [
            # (評価, 手帳種類, 手帳番号)
            (5, "physical", "P001"),
            (5, "physical", "P002"),
            (5, "intellectual", "I001"),
            (4, "intellectual", "I002"),
            (4, "mental", "M001"),
            (3, "mental", "M002"),
            (2, "other", "O001"),
            (2, "other", "O002"),
            (1, "physical", "P003"),
        ]

        for i, (rating, cert_type, cert_num) in enumerate(ratings_data):
            FacilityReview.objects.create(
                facility=self.facility,
                reviewer_name=f"テスト利用者{i+1}",
                certificate_type=cert_type,
                certificate_number=cert_num,
                rating=rating,
                comment="これはテストコメントです。",
                is_approved=True,
            )

    def test_get_facility_reviews(self):
        """get_facility_reviewsメソッドのテスト

        シナリオ:
        1. approval_filter=True（デフォルト）で承認済みレビューのみ取得できることを確認
        2. approval_filter=Falseで未承認レビューのみ取得できることを確認
        3. approval_filter=Noneですべてのレビュー（承認・未承認含む）が取得できることを確認
        """
        # 承認済みレビューの取得テスト
        reviews = ReviewRepository.get_facility_reviews(self.facility)
        self.assertEqual(reviews.count(), 9)  # 全レビュー数

        # 未承認のレビューを1件作成
        FacilityReview.objects.create(
            facility=self.facility,
            reviewer_name="未承認ユーザー",
            certificate_type="physical",
            certificate_number="P999",
            rating=3,
            comment="未承認のレビューです。",
            is_approved=False,
        )

        # 未承認のみのレビュー取得テスト (approval_filter=False)
        unapproved_reviews = ReviewRepository.get_facility_reviews(
            self.facility, approval_filter=False
        )
        self.assertEqual(unapproved_reviews.count(), 1)  # 未承認のレビューのみ

        # 全レビュー取得テスト (承認状態を問わない: approval_filter=None)
        all_reviews = ReviewRepository.get_facility_reviews(
            self.facility, approval_filter=None
        )
        self.assertEqual(all_reviews.count(), 10)  # 承認・未承認含む全レビュー
