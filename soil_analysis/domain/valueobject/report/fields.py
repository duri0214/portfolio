from dataclasses import dataclass


@dataclass(frozen=True)
class ReportField:
    """
    レポート項目の定義情報を保持するクラス。

    Attributes:
        key: フィールドのキー名（DBのカラム名に相当）
        label: 表示用のラベル名（アルファベット略称など）
        unit: 単位
        description: 項目名の日本語解説
    """

    key: str
    label: str
    unit: str
    description: str


REPORT_FIELDS: tuple[ReportField, ...] = (
    ReportField("ec", "EC", "mS/cm", "電気伝導率"),
    ReportField("nh4n", "NH4-N", "mg/100g", "アンモニア態窒素"),
    ReportField("no3n", "NO3-N", "mg/100g", "硝酸態窒素"),
    ReportField(
        "total_nitrogen",
        "無機態N",
        "mg/100g",
        "無機態窒素（NH4+NO3）",
    ),
    ReportField(
        "nh4_per_nitrogen",
        "NH4/N比",
        "",
        "アンモニア態窒素比",
    ),
    ReportField("ph", "pH", "", "水素イオン濃度"),
    ReportField("cao", "CaO", "mg/100g", "交換性石灰"),
    ReportField("mgo", "MgO", "mg/100g", "交換性苦土"),
    ReportField("k2o", "K2O", "mg/100g", "交換性加里"),
    ReportField(
        "base_saturation",
        "Base Saturation",
        "%",
        "塩基飽和度",
    ),
    ReportField("cao_per_mgo", "CaO/MgO", "", "CaO/MgO比"),
    ReportField("mgo_per_k2o", "MgO/K2O", "", "MgO/K2O比"),
    ReportField(
        "phosphorus_absorption",
        "リン酸吸",
        "mg/100g",
        "リン酸吸収係数",
    ),
    ReportField("p2o5", "P2O5", "mg/100g", "可給態リン酸"),
    ReportField("cec", "CEC", "meq/100g", "保肥力"),
    ReportField("humus", "Humus", "%", "腐植"),
    ReportField("bulk_density", "仮比重", "", "仮比重"),
)
