import unittest

from soil_analysis.domain.valueobject.report.chemical_assessment import (
    ChemicalAssessmentVO,
)
from soil_analysis.domain.valueobject.report.chemical_indicator import (
    BaseSaturationVO,
    CaoVO,
    CecVO,
    EcVO,
    HumusVO,
    K2oVO,
    MgoVO,
    Nh4nVO,
    No3nVO,
    P2o5VO,
    PhosphorusAbsorptionVO,
    PhVO,
)


class TestChemicalAssessmentVO(unittest.TestCase):
    def test_ph_assessment(self):
        """
        シナリオ:
        - 入力: pHが低め(5.5)、適正(6.5)、高め(7.5)の測定値。
        - 処理: pH指標の判定(assess)を実行。
        - 期待値: それぞれ「低(danger)」「適正(success)」「高(danger)」と判定されること。
        """
        # 低いpH
        vo = ChemicalAssessmentVO(ph=PhVO(5.5))
        res = vo.ph.assess()
        self.assertEqual(res.name, "pH(水素イオン濃度)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "danger")
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
        self.assertEqual(res.level, "danger")

    def test_ec_assessment(self):
        """
        シナリオ:
        - 入力: ECが低め(0.05)、適正(0.3)、過剰(0.6)の測定値。
        - 処理: EC指標の判定(assess)を実行。
        - 期待値: それぞれ「低(danger)」「適正(success)」「過剰(danger)」と判定されること。
        """
        # 低いEC
        vo = ChemicalAssessmentVO(ec=EcVO(0.05))
        res = vo.ec.assess()
        self.assertEqual(res.name, "EC(電気伝導率)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "danger")
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
        """
        シナリオ:
        - 入力: アンモニア態窒素が過剰(6.0)と適正(3.0)の測定値。
        - 処理: NH4-N指標の判定(assess)を実行。
        - 期待値: それぞれ「過剰(danger)」「適正(success)」と判定されること。
        """
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
        """
        シナリオ:
        - 入力: 硝酸態窒素が過剰(20.0)と適正(10.0)の測定値。
        - 処理: NO3-N指標の判定(assess)を実行。
        - 期待値: それぞれ「過剰(danger)」「適正(success)」と判定されること。
        """
        vo = ChemicalAssessmentVO(no3n=No3nVO(20.0))
        res = vo.no3n.assess()
        self.assertEqual(res.name, "NO3-N(硝酸態窒素)")
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(no3n=No3nVO(10.0))
        res = vo.no3n.assess()
        self.assertEqual(res.label, "適正")

    def test_cec_assessment(self):
        """
        シナリオ:
        - 入力: CECが低め(10.0)と適正(15.0)の測定値。
        - 処理: CEC指標の判定(assess)を実行。
        - 期待値: それぞれ「低(danger)」「適正(success)」と判定されること。
        """
        vo = ChemicalAssessmentVO(cec=CecVO(10.0))
        res = vo.cec.assess()
        self.assertEqual(res.name, "CEC(保肥力)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(cec=CecVO(15.0))
        res = vo.cec.assess()
        self.assertEqual(res.label, "適正")

    def test_base_saturation_assessment(self):
        """
        シナリオ:
        - 入力: 塩基飽和度が過剰(110, 90)、適正(70)、低め(50)の測定値。
        - 処理: 塩基飽和度指標の判定(assess)を実行。
        - 期待値: 80超は「過剰(danger)」、80以下は「適正(success)」、60以下は「低(danger)」と判定されること。
        """
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
        self.assertEqual(res.level, "danger")

    def test_p2o5_assessment(self):
        """
        シナリオ:
        - 入力: 可給態リン酸が低め(10.0)と過剰(120.0)の測定値。
        - 処理: P2O5指標の判定(assess)を実行。
        - 期待値: それぞれ「低(danger)」「過剰(danger)」と判定されること。
        """
        vo = ChemicalAssessmentVO(p2o5=P2o5VO(10.0))
        res = vo.p2o5.assess()
        self.assertEqual(res.name, "P2O5(可給態リン酸)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "danger")

        vo = ChemicalAssessmentVO(p2o5=P2o5VO(120.0))
        res = vo.p2o5.assess()
        self.assertEqual(res.label, "過剰")
        self.assertEqual(res.level, "danger")

    def test_humus_assessment(self):
        """
        シナリオ:
        - 入力: 腐植が低め(2.5)の測定値。
        - 処理: Humus指標の判定(assess)を実行。
        - 期待値: 「低(danger)」と判定されること。
        """
        vo = ChemicalAssessmentVO(humus=HumusVO(2.5))
        res = vo.humus.assess()
        self.assertEqual(res.name, "Humus(腐植)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "danger")

    def test_individual_salt_assessments(self):
        """
        シナリオ:
        - 入力: 交換性石灰(低)、交換性苦土(適正)、交換性加里(過剰)の測定値。
        - 処理: それぞれの指標の判定(assess)を実行。
        - 期待値: 正しいラベル(低、適正、過剰)が返されること。
        """
        # CaO
        vo = ChemicalAssessmentVO(cao=CaoVO(100.0))
        res = vo.cao.assess()
        self.assertEqual(res.name, "CaO(交換性石灰)")
        self.assertEqual(res.label, "低")
        self.assertEqual(res.level, "danger")

        # MgO
        vo = ChemicalAssessmentVO(mgo=MgoVO(40.0))
        res = vo.mgo.assess()
        self.assertEqual(res.name, "MgO(交換性苦土)")
        self.assertEqual(res.label, "適正")

        # K2O
        vo = ChemicalAssessmentVO(k2o=K2oVO(40.0))
        res = vo.k2o.assess()
        self.assertEqual(res.name, "K2O(交換性加里)")
        self.assertEqual(res.label, "過剰")

    def test_combination_logic(self):
        """
        シナリオ:
        - 入力: pH, EC, NO3-Nの組み合わせ（高pH低EC、低pH高EC、NO3-N過多）。
        - 処理: 相関判定(combination_assessments)を確認。
        - 期待値: 肥料不足、石灰過剰、肥料過剰、酸性化リスク、吸収阻害リスクが正しく判定され、レベルがdangerになること。
        """
        # 高pH低EC -> 石灰過剰 & 肥料不足
        vo = ChemicalAssessmentVO(ph=PhVO(7.5), ec=EcVO(0.05), no3n=No3nVO(5.0))
        assessments = {a.label: a.result for a in vo.combination_assessments}
        self.assertTrue(assessments["石灰成分の過剰"])
        self.assertTrue(assessments["肥料成分の不足"])
        self.assertFalse(assessments["肥料成分の過剰"])
        self.assertFalse(assessments["土壌の酸性化リスク"])
        self.assertFalse(assessments["成分吸収阻害リスク"])

        # レベルの確認
        levels = {a.label: a.level for a in vo.combination_assessments}
        self.assertEqual(levels["石灰成分の過剰"], "danger")
        self.assertEqual(levels["肥料成分の不足"], "danger")
        self.assertEqual(levels["肥料成分の過剰"], "success")

        # 低pH高EC -> 肥料過剰 & 酸性化リスク
        vo = ChemicalAssessmentVO(ph=PhVO(5.5), ec=EcVO(0.6), no3n=No3nVO(5.0))
        assessments = {a.label: a.result for a in vo.combination_assessments}
        self.assertFalse(assessments["石灰成分の過剰"])
        self.assertFalse(assessments["肥料成分の不足"])
        self.assertTrue(assessments["肥料成分の過剰"])
        self.assertTrue(assessments["土壌の酸性化リスク"])

        levels = {a.label: a.level for a in vo.combination_assessments}
        self.assertEqual(levels["肥料成分の過剰"], "danger")
        self.assertEqual(levels["土壌の酸性化リスク"], "danger")

        # 成分吸収阻害リスク（NO3-N過多）
        vo = ChemicalAssessmentVO(ph=PhVO(6.5), ec=EcVO(0.3), no3n=No3nVO(20.0))
        assessments = {a.label: a.result for a in vo.combination_assessments}
        self.assertTrue(assessments["成分吸収阻害リスク"])
        levels = {a.label: a.level for a in vo.combination_assessments}
        self.assertEqual(levels["成分吸収阻害リスク"], "danger")

    def test_from_measurements_averaging(self):
        """
        シナリオ:
        - 入力: 複数の測定データ（一部欠損を含む）。
        - 処理: from_measurements メソッドでVOを生成。
        - 期待値: 有効な値の平均値が計算され、VOに設定されること。
        """

        class MockMeasurement:
            def __init__(self, **kwargs):
                self.ph = kwargs.get("ph")
                self.ec = kwargs.get("ec")
                self.nh4n = kwargs.get("nh4n")
                self.no3n = kwargs.get("no3n")
                self.cec = kwargs.get("cec")
                self.base_saturation = kwargs.get("base_saturation")
                self.p2o5 = kwargs.get("p2o5")
                self.phosphorus_absorption = kwargs.get("phosphorus_absorption")
                self.humus = kwargs.get("humus")
                self.cao = kwargs.get("cao")
                self.mgo = kwargs.get("mgo")
                self.k2o = kwargs.get("k2o")

        measurements = [
            MockMeasurement(ph=6.0, ec=0.2, cao=100.0, phosphorus_absorption=1000.0),
            MockMeasurement(ph=7.0, ec=0.4, cao=200.0, phosphorus_absorption=1200.0),
            MockMeasurement(ph=None, ec=0.6, cao=None, phosphorus_absorption=None),
        ]

        vo = ChemicalAssessmentVO.from_measurements(measurements)
        self.assertAlmostEqual(vo.ph.value, 6.5)
        self.assertAlmostEqual(vo.ec.value, 0.4)
        self.assertAlmostEqual(vo.cao.value, 150.0)
        self.assertAlmostEqual(vo.phosphorus_absorption.value, 1100.0)

    def test_missing_data_summary(self):
        """
        シナリオ:
        - 入力: データが空のVO。
        - 処理: get_summary を実行。
        - 期待値: データ不足のメッセージが返されること。
        """
        vo = ChemicalAssessmentVO()
        self.assertEqual(vo.get_summary(), "判定に必要なデータが不足しています。")

    def test_warnings(self):
        """
        シナリオ:
        - 入力: 各項目が異常値（塩基飽和度過剰、腐植不足、リン酸過剰、窒素過剰）のVO。
        - 処理: get_warnings を実行。
        - 期待値: それぞれの異常に対する警告メッセージが含まれていること。
        """
        # 塩基飽和度過剰、腐植不足、リン酸過剰、窒素過剰のケース
        vo = ChemicalAssessmentVO(
            base_saturation=BaseSaturationVO(120.0),
            humus=HumusVO(2.0),
            p2o5=P2o5VO(120.0),
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

    def test_phosphorus_absorption_assessment(self):
        """
        シナリオ:
        - 入力: リン酸吸収係数(1000.0)の測定値。
        - 処理: 判定(assess)を実行。
        - 期待値: 「参照(info)」レベルで判定されること。
        """
        vo = ChemicalAssessmentVO(phosphorus_absorption=PhosphorusAbsorptionVO(1000.0))
        res = vo.phosphorus_absorption.assess()
        self.assertEqual(res.name, "リン酸吸(リン酸吸収係数)")
        self.assertEqual(res.label, "参照")
        self.assertEqual(res.level, "info")
        self.assertIn("適正なリン酸施用量", res.comment)

    def test_reference_vo(self):
        """
        シナリオ:
        - 入力: 判定基準のない項目(ReferenceVO)。
        - 処理: 判定(assess)を実行。
        - 期待値: 常に「参照(info)」レベルで判定されること。
        """
        from soil_analysis.domain.valueobject.report.chemical_indicator import (
            ReferenceVO,
        )

        vo = ReferenceVO(value=1.23, key="custom_key")
        res = vo.assess()
        self.assertEqual(res.label, "参照")
        self.assertEqual(res.level, "info")
