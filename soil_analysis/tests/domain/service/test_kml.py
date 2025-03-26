from unittest import TestCase

from soil_analysis.domain.service.kml import KmlService


class TestKmlService(TestCase):
    def test_parse_kml(self):
        kml_str = """
        <?xml version="1.0" encoding="UTF-8"?>
        <kml>
          <Document id="featureCollection">
            <Placemark id="06ad0c86-6cba-46a6-a7f8-11117fb75634">
              <name>株式会社ABC_ABCグループ - ススムA1</name>
              <MultiGeometry>
                <Polygon>
                  <outerBoundaryIs>
                    <LinearRing>
                      <coordinates>137.6489657,34.7443565 137.6491266,34.744123 137.648613,34.7438929 
                      137.6484413,34.7441175 137.6489657,34.7443565</coordinates>
                    </LinearRing>
                  </outerBoundaryIs>
                </Polygon>
              </MultiGeometry>
            </Placemark>
            <Placemark id="0d681402-ae55-4406-9582-6c9360bc5e5b">
              <name>株式会社ABC_ABCグループ - ススムA3</name>
              <MultiGeometry>
                <Polygon>
                  <outerBoundaryIs>
                    <LinearRing>
                      <coordinates>137.6492809,34.743865 137.6494646,34.7436029 137.6489644,34.7433683 
                      137.6487806,34.7436403 137.6492809,34.743865</coordinates>
                    </LinearRing>
                  </outerBoundaryIs>
                </Polygon>
              </MultiGeometry>
            </Placemark>
          </Document>
        </kml>
        """

        kml_service = KmlService()
        land_locations = kml_service.parse_kml(kml_str)

        # パース結果の確認
        self.assertIsInstance(land_locations, list)
        self.assertEqual(2, len(land_locations))

        # 個別の領域の確認
        self.assertEqual("株式会社ABC_ABCグループ - ススムA1", land_locations[0].name)
        self.assertAlmostEqual(
            137.6487867, land_locations[0].center.longitude, delta=0.000001
        )
        self.assertAlmostEqual(
            34.7441225, land_locations[0].center.latitude, delta=0.000001
        )

        self.assertEqual("株式会社ABC_ABCグループ - ススムA3", land_locations[1].name)
        self.assertAlmostEqual(
            137.6491226, land_locations[1].center.longitude, delta=0.000001
        )
        self.assertAlmostEqual(
            34.7436191, land_locations[1].center.latitude, delta=0.000001
        )
