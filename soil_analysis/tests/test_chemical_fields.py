from django.test import SimpleTestCase

from soil_analysis.domain.valueobject.chemical_report.fields import (
    CHEMICAL_FIELD_ALIAS_TO_KEY,
    CHEMICAL_FIELD_DEFINITIONS,
    CHEMICAL_FIELD_KEYS,
    normalize_text,
)
from soil_analysis.models import LandScoreChemical


class ChemicalFieldDefinitionTests(SimpleTestCase):
    def test_all_field_keys_exist_in_land_score_chemical_model(self):
        model_field_names = {
            field.name
            for field in LandScoreChemical._meta.get_fields()
            if getattr(field, "attname", None)
        }
        for key in CHEMICAL_FIELD_KEYS:
            self.assertIn(key, model_field_names)

    def test_alias_resolution_returns_expected_keys(self):
        self.assertEqual(CHEMICAL_FIELD_ALIAS_TO_KEY.get(normalize_text("NH4-N")), "nh4n")
        self.assertEqual(CHEMICAL_FIELD_ALIAS_TO_KEY.get(normalize_text("no3n")), "no3n")
        self.assertEqual(CHEMICAL_FIELD_ALIAS_TO_KEY.get(normalize_text(" P2O5 ")), "p2o5")
        self.assertEqual(CHEMICAL_FIELD_ALIAS_TO_KEY.get(normalize_text("リン酸吸収係数")), "phosphorus_absorption")
        self.assertIsNone(CHEMICAL_FIELD_ALIAS_TO_KEY.get(normalize_text("unknown-column")))

    def test_major_display_labels_and_units(self):
        by_key = {field.key: field for field in CHEMICAL_FIELD_DEFINITIONS}
        self.assertEqual(by_key["ec"].label, "EC")
        self.assertEqual(by_key["ec"].unit, "mS/cm")
        self.assertEqual(by_key["cec"].label, "CEC")
        self.assertEqual(by_key["cec"].unit, "meq/100g")
