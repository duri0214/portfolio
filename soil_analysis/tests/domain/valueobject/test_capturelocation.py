from unittest import TestCase

from soil_analysis.domain.valueobject.capturelocation import CaptureLocation


class TestCaptureLocation(TestCase):
    def setUp(self):
        """
        Note: テスト要件 座標はxarvioベース(lng,lat)で記す
          撮影位置の座標は 137.6492809,34.743865 とする（ススムA2とススムA3の中点を google maps で調べた）
          撮影位置の座標から、ススムA3の中心点（137.64910916605962,34.74362556670041）に向かって、
          言い換えると方位角190に向かって10m進んだ先の座標は約 137.64923,34.74378 となるはずである
          ※補正後座標を算出してみて10m先の座標を google maps においてみてフィードバックを繰り返した
        """
        # 撮影位置の座標と方位角
        self.capture_point_lng = 137.6492809
        self.capture_point_lat = 34.743865
        self.capture_point_azimuth = 190

    def test_capture_location(self):
        capture_location = CaptureLocation(
            longitude=self.capture_point_lng,
            latitude=self.capture_point_lat,
            azimuth=self.capture_point_azimuth,
        )
        self.assertAlmostEqual(
            self.capture_point_lng,
            capture_location.original_position.to_tuple()[0],
            delta=0.0003,
        )
        self.assertAlmostEqual(
            self.capture_point_lat,
            capture_location.original_position.to_tuple()[1],
            delta=0.0003,
        )

    def test_corrected_coord(self):
        capture_location = CaptureLocation(
            self.capture_point_lng, self.capture_point_lat, self.capture_point_azimuth
        )
        print(f"gmap検証用_撮影位置: 34.743865,137.6492809")
        print(
            f"gmap検証用_10m先の位置: {capture_location.adjusted_position.to_google().to_tuple()}"
        )
        self.assertAlmostEqual(
            137.6492, capture_location.adjusted_position.to_tuple()[1], delta=0.0003
        )
        self.assertAlmostEqual(
            34.74378, capture_location.adjusted_position.to_tuple()[0], delta=0.0003
        )
