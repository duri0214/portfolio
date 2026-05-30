from dataclasses import dataclass
from typing import Any

from .chemical_indicator import (
    BaseSaturationVO,
    CaoVO,
    CecVO,
    EcVO,
    HumusVO,
    ItemAssessment,
    K2oVO,
    MgoVO,
    Nh4nVO,
    No3nVO,
    P2o5VO,
    PhVO,
    PhosphorusAbsorptionVO,
)


@dataclass(frozen=True)
class CombinationAssessment:
    """
    項目間の相関判定結果

    Attributes:
        label: 判定項目ラベル
        result: 判定結果 (Trueの場合、該当する状態であることを示す)
        condition: 判定条件のテキスト表現
        description: 判定内容の詳細説明
    """

    label: str
    result: bool
    condition: str
    description: str


@dataclass(frozen=True)
class ChemicalAssessmentVO:
    """
    化学分析値に基づく判定生成を行うValue Object

    Attributes:
        ph: pH(水素イオン濃度)
        ec: EC(電気伝導率)
        nh4n: NH4-N(アンモニア態窒素)
        no3n: NO3-N(硝酸態窒素)
        cec: CEC(保肥力)
        base_saturation: Base Saturation(塩基飽和度)
        p2o5: P2O5(可給態リン酸)
        phosphorus_absorption: リン酸吸収係数
        humus: Humus(腐植)
        cao: CaO(交換性石灰)
        mgo: MgO(交換性苦土)
        k2o: K2O(交換性加里)
    """

    ph: PhVO = PhVO(None)
    ec: EcVO = EcVO(None)
    nh4n: Nh4nVO = Nh4nVO(None)
    no3n: No3nVO = No3nVO(None)
    cec: CecVO = CecVO(None)
    base_saturation: BaseSaturationVO = BaseSaturationVO(None)
    p2o5: P2o5VO = P2o5VO(None)
    phosphorus_absorption: PhosphorusAbsorptionVO = PhosphorusAbsorptionVO(None)
    humus: HumusVO = HumusVO(None)
    cao: CaoVO = CaoVO(None)
    mgo: MgoVO = MgoVO(None)
    k2o: K2oVO = K2oVO(None)

    @classmethod
    def from_measurements(cls, measurements: list[Any]) -> "ChemicalAssessmentVO":
        """
        複数の測定データから平均値を算出してVOを生成する。
        欠損値は集約時に除外する。
        """
        if not measurements:
            return cls()

        def avg(attr: str) -> float | None:
            values = [
                getattr(m, attr) for m in measurements if getattr(m, attr) is not None
            ]
            if not values:
                return None
            return sum(values) / len(values)

        return cls(
            ph=PhVO(avg("ph")),
            ec=EcVO(avg("ec")),
            nh4n=Nh4nVO(avg("nh4n")),
            no3n=No3nVO(avg("no3n")),
            cec=CecVO(avg("cec")),
            base_saturation=BaseSaturationVO(avg("base_saturation")),
            p2o5=P2o5VO(avg("p2o5")),
            phosphorus_absorption=PhosphorusAbsorptionVO(avg("phosphorus_absorption")),
            humus=HumusVO(avg("humus")),
            cao=CaoVO(avg("cao")),
            mgo=MgoVO(avg("mgo")),
            k2o=K2oVO(avg("k2o")),
        )

    @property
    def combination_assessments(self) -> list[CombinationAssessment]:
        """
        項目間の相関判定（横断的なドメインロジック）を個別のチェックポイントとして返す

        判定内容:
        - 肥料成分の不足: ECが低く、全体的に肥料成分が不足している可能性があります。
        - 肥料成分の過剰: ECが高く、肥料過多（塩類集積）の可能性があります。
        - 石灰成分の過剰: pHが高く、石灰分が過剰な可能性があります。
        - 土壌の酸性化リスク: pHが低くECが高い場合、窒素肥料の過剰投入による酸性化が進んでいる可能性があります。
        - 成分吸収阻害リスク: 硝酸態窒素（NO3-N）やECが非常に高い場合、成分吸収阻害の恐れがあります。
        """
        results = []
        if self.ph.value is None or self.ec.value is None:
            return results

        # 肥料成分の不足
        results.append(
            CombinationAssessment(
                label="肥料成分の不足",
                result=self.ec.is_low(),
                condition=f"EC < {self.ec.LOW}",
                description="ECが低く、全体的に肥料成分が不足している可能性があります。",
            )
        )
        # 肥料成分の過剰
        results.append(
            CombinationAssessment(
                label="肥料成分の過剰",
                result=self.ec.is_high(),
                condition=f"EC > {self.ec.HIGH}",
                description="ECが高く、肥料過多（塩類集積）の可能性があります。",
            )
        )
        # 石灰成分の過剰
        results.append(
            CombinationAssessment(
                label="石灰成分の過剰",
                result=self.ph.is_high(),
                condition=f"pH > {self.ph.HIGH}",
                description="pHが高く、石灰分が過剰な可能性があります。他の成分の吸収阻害を招く恐れがあります。",
            )
        )
        # 土壌の酸性化リスク
        results.append(
            CombinationAssessment(
                label="土壌の酸性化リスク",
                result=self.ph.is_low() and self.ec.is_high(),
                condition=f"pH < {self.ph.LOW} かつ EC > {self.ec.HIGH}",
                description="pHが低くECが高い場合、窒素肥料の過剰投入による酸性化が進んでいる可能性があります。",
            )
        )
        # 窒素過多による成分吸収阻害リスク
        results.append(
            CombinationAssessment(
                label="成分吸収阻害リスク",
                result=self.no3n.is_high()
                or (self.ec.value is not None and self.ec.value > 1.0),
                condition=f"NO3-N > {self.no3n.UPPER_LIMIT} または EC > 1.0",
                description="硝酸態窒素（NO3-N）やECが非常に高い場合、作物が苦土や鉄などの成分をうまく吸収できなくなる可能性があります。",
            )
        )
        return results

    def get_combination_comments(self) -> list[str]:
        """
        有効な相関判定（判定結果が True のもの）の説明文リストを返す。
        """
        return [r.description for r in self.combination_assessments if r.result]

    @property
    def combination_items_label(self) -> str:
        """横断判定の対象項目ラベル"""
        return "pH・ECの相関"

    def get_warnings(self) -> list[str]:
        """
        注意が必要な項目（判定レベルが danger のもの）を警告メッセージとして抽出する。
        """
        warnings = []

        # 個別の判定結果を走査して danger レベルのものを警告に追加
        for res in self.results.values():
            if res.level == "danger":
                # すでに個別に詳細なメッセージを定義しているもの（現在は腐植のみ）は除外するか、
                # あるいは一律で生成して補足する
                if "Humus" in res.name:
                    continue

                # 単位を取得するためにフィールド定義を参照
                # res.name には "label(description)" が入っている
                warnings.append(
                    f"警告：{res.name}が{res.label}です（{res.value:.1f}）。"
                )

        # 特殊なアドバイスを伴う警告
        if self.humus.is_low():
            name = self.humus.assess().name
            warnings.append(
                f"警告：{name}が{self.humus.value:.1f}%と不足しています。堆肥の投入を推奨します。"
            )

        return warnings

    def get_summary(self) -> str:
        """
        土壌診断結果を要約した文章を生成する。
        相関判定の結果を優先し、特に問題がない場合は pH と EC の状態に基づいたメッセージを返す。
        """
        if all(
            v.value is None
            for v in [
                self.ph,
                self.ec,
                self.nh4n,
                self.no3n,
                self.cec,
                self.base_saturation,
                self.p2o5,
                self.humus,
                self.cao,
                self.mgo,
                self.k2o,
            ]
        ):
            return "判定に必要なデータが不足しています。"

        combos = self.get_combination_comments()
        if combos:
            return " ".join(combos)

        ph_res = self.ph.assess()
        ec_res = self.ec.assess()
        if ph_res.label == "適正" and ec_res.label == "適正":
            return "pH・ECともに適正範囲内です。良好な状態を維持してください。"

        return f"土壌診断の結果、{ph_res.label if ph_res.label != '適正' else ''}{'・' if ph_res.label != '適正' and ec_res.label != '適正' else ''}{ec_res.label if ec_res.label != '適正' else ''}な状態が見受けられます。詳細は各項目を確認してください。"

    @property
    def results(self) -> dict[str, ItemAssessment]:
        """全項目の個別判定結果を辞書形式で取得する"""
        return {
            "ph": self.ph.assess(),
            "ec": self.ec.assess(),
            "nh4n": self.nh4n.assess(),
            "no3n": self.no3n.assess(),
            "cec": self.cec.assess(),
            "base_saturation": self.base_saturation.assess(self.cec.value),
            "p2o5": self.p2o5.assess(),
            "phosphorus_absorption": self.phosphorus_absorption.assess(),
            "humus": self.humus.assess(),
            "cao": self.cao.assess(),
            "mgo": self.mgo.assess(),
            "k2o": self.k2o.assess(),
        }

    @property
    def categorized_results(self) -> dict[str, list[ItemAssessment]]:
        """
        判定結果をカテゴリー（窒素・EC、塩基類、リン酸、土壌ポテンシャル）ごとに分類して返す。
        レポート表示などで利用される。
        """
        return {
            "窒素・EC関連": [
                self.ec.assess(),
                self.nh4n.assess(),
                self.no3n.assess(),
            ],
            "塩基類関連": [
                self.ph.assess(),
                self.base_saturation.assess(self.cec.value),
                self.cao.assess(),
                self.mgo.assess(),
                self.k2o.assess(),
            ],
            "リン酸関連": [
                self.p2o5.assess(),
                self.phosphorus_absorption.assess(),
            ],
            "土壌ポテンシャル関連": [
                self.cec.assess(),
                self.humus.assess(),
            ],
        }
