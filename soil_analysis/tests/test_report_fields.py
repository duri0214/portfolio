from django.test import SimpleTestCase

from soil_analysis.domain.valueobject.report.fields import (
    REPORT_FIELDS,
)
from soil_analysis.models import SoilChemicalMeasurement


class FieldDefinitionTests(SimpleTestCase):
    def test_all_field_keys_exist_in_soil_chemical_measurement_model(self):
        for report_field in REPORT_FIELDS:
            # フィールドまたはプロパティとして存在することを確認
            self.assertTrue(
                hasattr(SoilChemicalMeasurement, report_field.key),
                f"Field or property '{report_field.key}' not found in SoilChemicalMeasurement model",
            )

    def test_major_display_labels_and_units(self):
        by_key = {report_field.key: report_field for report_field in REPORT_FIELDS}
        self.assertEqual(by_key["ec"].label, "EC")
        self.assertEqual(by_key["ec"].unit, "mS/cm")
        self.assertEqual(by_key["cec"].label, "CEC")
        self.assertEqual(by_key["cec"].unit, "meq/100g")
