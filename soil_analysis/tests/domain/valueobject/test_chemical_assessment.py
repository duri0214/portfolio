import unittest

from soil_analysis.domain.valueobject.report.chemical_assessment import (
    ChemicalAssessmentVO,
)
from soil_analysis.domain.valueobject.report.chemical_indicator import (
    BaseSaturationVO,
    CecVO,
    EcVO,
    HumusVO,
    Nh4nVO,
    No3nVO,
    P2o5VO,
    PhVO,
    ReferenceVO,
)


class TestChemicalAssessmentVO(unittest.TestCase):
    def test_ph_assessment(self):
        # 低いpH
        vo = ChemicalAssessmentVO(ph=PhVO(5.5))
        res = vo.ph.assess()
        self.assertEqual(res.name, "pH(水素イオン濃度)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "warning")
        self.assertEqual(res.min_threshold, 6.0)
        self.assertEqual(res.max_threshold, 7.0)

        # 適正なpH
        vo = ChemicalAssessmentVO(ph=PhVO(6.5))
        res = vo.ph.assess()
        self.assertEqual(res.label, "適正")
        self.assertEqual(res.level, "success")
        self.assertEqual(res.min_threshold, 6.0)
        self.assertEqual(res.max_threshold, 7.0)

        # 高いpH
        vo = ChemicalAssessmentVO(ph=PhVO(7.5))
        res = vo.ph.assess()
        self.assertEqual(res.label, "高")
        self.assertEqual(res.level, "warning")

    def test_ec_assessment(self):
        # 低いEC
        vo = ChemicalAssessmentVO(ec=EcVO(0.05))
        res = vo.ec.assess()
        self.assertEqual(res.name, "EC(電気伝導率)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.min_threshold, 0.1)
        self.assertEqual(res.max_threshold, 0.5)

        # 適正なEC
        vo = ChemicalAssessmentVO(ec=EcVO(0.3))
        res = vo.ec.assess()
        self.assertEqual(res.label, "適正")
        self.assertEqual(res.min_threshold, 0.1)
        self.assertEqual(res.max_threshold, 0.5)

        # 高いEC
        vo = ChemicalAssessmentVO(ec=EcVO(0.6))
        res = vo.ec.assess()
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

    def test_nh4n_assessment(self):
        vo = ChemicalAssessmentVO(nh4n=Nh4nVO(6.0))
        res = vo.nh4n.assess()
        self.assertEqual(res.name, "NH4-N(アンモニア態窒素)")
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")
        self.assertIsNone(res.min_threshold)
        self.assertEqual(res.max_threshold, 5.0)

        vo = ChemicalAssessmentVO(nh4n=Nh4nVO(3.0))
        res = vo.nh4n.assess()
        self.assertEqual(res.label, "適正")
        self.assertIsNone(res.min_threshold)
        self.assertEqual(res.max_threshold, 5.0)

    def test_no3n_assessment(self):
        vo = ChemicalAssessmentVO(no3n=No3nVO(20.0))
        res = vo.no3n.assess()
        self.assertEqual(res.name, "NO3-N(硝酸態窒素)")
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(no3n=No3nVO(10.0))
        res = vo.no3n.assess()
        self.assertEqual(res.label, "適正")

    def test_cec_assessment(self):
        vo = ChemicalAssessmentVO(cec=CecVO(10.0))
        res = vo.cec.assess()
        self.assertEqual(res.name, "CEC(保肥力)")
        self.assertEqual(res.label, "低")

        vo = ChemicalAssessmentVO(cec=CecVO(15.0))
        res = vo.cec.assess()
        self.assertEqual(res.label, "適正")

    def test_base_saturation_assessment(self):
        vo = ChemicalAssessmentVO(base_saturation=BaseSaturationVO(110.0))
        res = vo.base_saturation.assess()
        self.assertEqual(res.name, "Base Saturation(塩基飽和度)")
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(base_saturation=BaseSaturationVO(90.0))
        res = vo.base_saturation.assess()
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(base_saturation=BaseSaturationVO(70.0))
        res = vo.base_saturation.assess()
        self.assertEqual(res.label, "適正")

        vo = ChemicalAssessmentVO(base_saturation=BaseSaturationVO(50.0))
        res = vo.base_saturation.assess()
        self.assertEqual(res.label, "低")

    def test_p2o5_assessment(self):
        vo = ChemicalAssessmentVO(p2o5=P2o5VO(5.0))
        res = vo.p2o5.assess()
        self.assertEqual(res.name, "P2O5(可給態リン酸)")
        self.assertEqual(res.label, "低")

        vo = ChemicalAssessmentVO(p2o5=P2o5VO(40.0))
        res = vo.p2o5.assess()
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

    def test_humus_assessment(self):
        vo = ChemicalAssessmentVO(humus=HumusVO(2.5))
        res = vo.humus.assess()
        self.assertEqual(res.name, "Humus(腐植)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "danger")

    def test_individual_salt_assessments(self):
        # CaO
        vo = ChemicalAssessmentVO(cao=ReferenceVO(100.0, "cao"))
        res = vo.cao.assess()
        self.assertEqual(res.name, "CaO(交換性石灰)")
        self.assertEqual(res.label, "参照")
        self.assertEqual(res.level, "secondary")

        # MgO
        vo = ChemicalAssessmentVO(mgo=ReferenceVO(50.0, "mgo"))
        res = vo.mgo.assess()
        self.assertEqual(res.name, "MgO(交換性苦土)")
        self.assertEqual(res.label, "参照")

        # K2O
        vo = ChemicalAssessmentVO(k2o=ReferenceVO(20.0, "k2o"))
        res = vo.k2o.assess()
        self.assertEqual(res.name, "K2O(交換性加里)")
        self.assertEqual(res.label, "参照")

    def test_combination_logic(self):
        # 高pH低EC -> 石灰過剰 & 肥料不足
        vo = ChemicalAssessmentVO(ph=PhVO(7.5), ec=EcVO(0.05))
        assessments = {a.label: a.result for a in vo.combination_assessments}
        self.assertTrue(assessments["石灰成分の過剰"])
        self.assertTrue(assessments["肥料成分の不足"])
        self.assertFalse(assessments["肥料成分の過剰"])
        self.assertFalse(assessments["土壌の酸性化リスク"])

        # 高pH高EC -> 石灰過剰 & 肥料過剰
        vo = ChemicalAssessmentVO(ph=PhVO(7.5), ec=EcVO(0.6))
        assessments = {a.label: a.result for a in vo.combination_assessments}
        self.assertTrue(assessments["石灰成分の過剰"])
        self.assertFalse(assessments["肥料成分の不足"])
        self.assertTrue(assessments["肥料成分の過剰"])
        self.assertFalse(assessments["土壌の酸性化リスク"])

        # 低pH低EC -> 肥料不足
        vo = ChemicalAssessmentVO(ph=PhVO(5.5), ec=EcVO(0.05))
        assessments = {a.label: a.result for a in vo.combination_assessments}
        self.assertFalse(assessments["石灰成分の過剰"])
        self.assertTrue(assessments["肥料成分の不足"])
        self.assertFalse(assessments["肥料成分の過剰"])
        self.assertFalse(assessments["土壌の酸性化リスク"])

        # 低pH高EC -> 肥料過剰 & 酸性化リスク
        vo = ChemicalAssessmentVO(ph=PhVO(5.5), ec=EcVO(0.6))
        assessments = {a.label: a.result for a in vo.combination_assessments}
        self.assertFalse(assessments["石灰成分の過剰"])
        self.assertFalse(assessments["肥料成分の不足"])
        self.assertTrue(assessments["肥料成分の過剰"])
        self.assertTrue(assessments["土壌の酸性化リスク"])

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
                self.cao = kwargs.get("cao")
                self.mgo = kwargs.get("mgo")
                self.k2o = kwargs.get("k2o")

        measurements = [
            MockMeasurement(ph=6.0, ec=0.2, cao=100.0),
            MockMeasurement(ph=7.0, ec=0.4, cao=200.0),
            MockMeasurement(ph=None, ec=0.6, cao=None),
        ]

        vo = ChemicalAssessmentVO.from_measurements(measurements)
        self.assertAlmostEqual(vo.ph.value, 6.5)
        self.assertAlmostEqual(vo.ec.value, 0.4)
        self.assertAlmostEqual(vo.cao.value, 150.0)

    def test_missing_data_summary(self):
        vo = ChemicalAssessmentVO()
        self.assertEqual(vo.get_summary(), "判定に必要なデータが不足しています。")

    def test_warnings(self):
        # 塩基飽和度過剰、腐植不足、リン酸過剰、窒素過剰のケース
        vo = ChemicalAssessmentVO(
            base_saturation=BaseSaturationVO(120.0),
            humus=HumusVO(2.0),
            p2o5=P2o5VO(40.0),
            nh4n=Nh4nVO(6.0),
        )
        warnings = vo.get_warnings()
        self.assertTrue(any("塩基飽和度" in w for w in warnings))
        self.assertTrue(any("腐植" in w for w in warnings))
        self.assertTrue(any("可給態リン酸" in w for w in warnings))
        self.assertTrue(any("アンモニア態窒素" in w for w in warnings))
        self.assertGreaterEqual(len(warnings), 4)

        # 境界値のテスト: 塩基飽和度が high(>80) だが over(>100) ではない場合も警告に出るべき
        vo = ChemicalAssessmentVO(base_saturation=BaseSaturationVO(90.0))
        warnings = vo.get_warnings()
        self.assertTrue(any("塩基飽和度" in w for w in warnings))

    def test_categorized_results(self):
        vo = ChemicalAssessmentVO(
            ph=PhVO(6.5), ec=EcVO(0.3), p2o5=P2o5VO(20.0), cec=CecVO(15.0)
        )
        categorized = vo.categorized_results
        self.assertIn("窒素・EC関連", categorized)
        self.assertIn("塩基類関連", categorized)
        self.assertIn("リン酸関連", categorized)
        self.assertIn("土壌ポテンシャル関連", categorized)
        self.assertNotIn("その他", categorized)

        self.assertEqual(len(categorized["窒素・EC関連"]), 3)  # EC, NH4, NO3
        self.assertEqual(
            len(categorized["塩基類関連"]), 5
        )  # pH, Base Saturation, CaO, MgO, K2O
        self.assertEqual(len(categorized["リン酸関連"]), 1)  # P2O5
        self.assertEqual(len(categorized["土壌ポテンシャル関連"]), 2)  # CEC, Humus
