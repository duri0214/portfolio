import unittest

from soil_analysis.domain.valueobject.chemical_assessment import ChemicalAssessmentVO


class TestChemicalAssessmentVO(unittest.TestCase):
    def test_ph_assessment(self):
        # 低いpH
        vo = ChemicalAssessmentVO(ph=5.5)
        res = vo.assess_ph()
        self.assertEqual(res.name, "pH(水素イオン濃度)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "warning")
        self.assertEqual(res.min_threshold, 6.0)
        self.assertEqual(res.max_threshold, 7.0)

        # 適正なpH
        vo = ChemicalAssessmentVO(ph=6.5)
        res = vo.assess_ph()
        self.assertEqual(res.label, "適正")
        self.assertEqual(res.level, "success")
        self.assertEqual(res.min_threshold, 6.0)
        self.assertEqual(res.max_threshold, 7.0)

        # 高いpH
        vo = ChemicalAssessmentVO(ph=7.5)
        res = vo.assess_ph()
        self.assertEqual(res.label, "高")
        self.assertEqual(res.level, "warning")

    def test_ec_assessment(self):
        # 低いEC
        vo = ChemicalAssessmentVO(ec=0.05)
        res = vo.assess_ec()
        self.assertEqual(res.name, "EC(電気伝導率)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.min_threshold, 0.1)
        self.assertEqual(res.max_threshold, 0.5)

        # 適正なEC
        vo = ChemicalAssessmentVO(ec=0.3)
        res = vo.assess_ec()
        self.assertEqual(res.label, "適正")
        self.assertEqual(res.min_threshold, 0.1)
        self.assertEqual(res.max_threshold, 0.5)

        # 高いEC
        vo = ChemicalAssessmentVO(ec=0.6)
        res = vo.assess_ec()
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

    def test_nh4n_assessment(self):
        vo = ChemicalAssessmentVO(nh4n=6.0)
        res = vo.assess_nh4n()
        self.assertEqual(res.name, "NH4-N(アンモニア態窒素)")
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")
        self.assertIsNone(res.min_threshold)
        self.assertEqual(res.max_threshold, 5.0)

        vo = ChemicalAssessmentVO(nh4n=3.0)
        res = vo.assess_nh4n()
        self.assertEqual(res.label, "適正")
        self.assertIsNone(res.min_threshold)
        self.assertEqual(res.max_threshold, 5.0)

    def test_no3n_assessment(self):
        vo = ChemicalAssessmentVO(no3n=20.0)
        res = vo.assess_no3n()
        self.assertEqual(res.name, "NO3-N(硝酸態窒素)")
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(no3n=10.0)
        res = vo.assess_no3n()
        self.assertEqual(res.label, "適正")

    def test_cec_assessment(self):
        vo = ChemicalAssessmentVO(cec=10.0)
        res = vo.assess_cec()
        self.assertEqual(res.name, "CEC(保肥力)")
        self.assertEqual(res.label, "低")

        vo = ChemicalAssessmentVO(cec=15.0)
        res = vo.assess_cec()
        self.assertEqual(res.label, "適正")

    def test_base_saturation_assessment(self):
        vo = ChemicalAssessmentVO(base_saturation=110.0)
        res = vo.assess_base_saturation()
        self.assertEqual(res.name, "Base Saturation(塩基飽和度)")
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(base_saturation=90.0)
        res = vo.assess_base_saturation()
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(base_saturation=70.0)
        res = vo.assess_base_saturation()
        self.assertEqual(res.label, "適正")

        vo = ChemicalAssessmentVO(base_saturation=50.0)
        res = vo.assess_base_saturation()
        self.assertEqual(res.label, "低")

    def test_p2o5_assessment(self):
        vo = ChemicalAssessmentVO(p2o5=5.0)
        res = vo.assess_p2o5()
        self.assertEqual(res.name, "P2O5(可給態リン酸)")
        self.assertEqual(res.label, "低")

        vo = ChemicalAssessmentVO(p2o5=40.0)
        res = vo.assess_p2o5()
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

    def test_humus_assessment(self):
        vo = ChemicalAssessmentVO(humus=2.5)
        res = vo.assess_humus()
        self.assertEqual(res.name, "Humus(腐植)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "danger")

    def test_combination_logic(self):
        # 高pH低EC
        vo = ChemicalAssessmentVO(ph=7.5, ec=0.05)
        comments = vo.get_combination_comments()
        self.assertTrue(any("高pHかつ低EC" in c for c in comments))

        # 高pH高EC
        vo = ChemicalAssessmentVO(ph=7.5, ec=0.6)
        comments = vo.get_combination_comments()
        self.assertTrue(any("高pHかつ高EC" in c for c in comments))

        # 低pH低EC
        vo = ChemicalAssessmentVO(ph=5.5, ec=0.05)
        comments = vo.get_combination_comments()
        self.assertTrue(any("低pHかつ低EC" in c for c in comments))

        # 低pH高EC
        vo = ChemicalAssessmentVO(ph=5.5, ec=0.6)
        comments = vo.get_combination_comments()
        self.assertTrue(any("低pHかつ高EC" in c for c in comments))

    def test_from_measurements_averaging(self):
        class MockMeasurement:
            def __init__(self, **kwargs):
                self.ph = kwargs.get("ph")
                self.ec = kwargs.get("ec")
                self.nh4n = kwargs.get("nh4n")
                self.no3n = kwargs.get("no3n")
                self.cec = kwargs.get("cec")
                self.base_saturation = kwargs.get("base_saturation")
                self.p2o5 = kwargs.get("p2o5")
                self.humus = kwargs.get("humus")

        measurements = [
            MockMeasurement(ph=6.0, ec=0.2),
            MockMeasurement(ph=7.0, ec=0.4),
            MockMeasurement(ph=None, ec=0.6),
        ]

        vo = ChemicalAssessmentVO.from_measurements(measurements)
        self.assertAlmostEqual(vo.ph, 6.5)
        self.assertAlmostEqual(vo.ec, 0.4)

    def test_missing_data_summary(self):
        vo = ChemicalAssessmentVO()
        self.assertEqual(vo.get_summary(), "判定に必要なデータが不足しています。")

    def test_warnings(self):
        vo = ChemicalAssessmentVO(base_saturation=120.0, humus=2.0)
        warnings = vo.get_warnings()
        self.assertEqual(len(warnings), 2)
        self.assertTrue(any("塩基飽和度" in w for w in warnings))
        self.assertTrue(any("腐植" in w for w in warnings))

    def test_categorized_results(self):
        vo = ChemicalAssessmentVO(ph=6.5, ec=0.3, p2o5=20.0, cec=15.0)
        categorized = vo.categorized_results
        self.assertIn("窒素・EC関連", categorized)
        self.assertIn("塩基類関連", categorized)
        self.assertIn("リン酸関連", categorized)
        self.assertIn("土壌ポテンシャル関連", categorized)

        self.assertEqual(len(categorized["窒素・EC関連"]), 3)  # EC, NH4, NO3
        self.assertEqual(len(categorized["塩基類関連"]), 2)  # pH, Base Saturation
        self.assertEqual(len(categorized["リン酸関連"]), 1)  # P2O5
        self.assertEqual(len(categorized["土壌ポテンシャル関連"]), 2)  # CEC, Humus
