from dataclasses import dataclass

import unicodedata


@dataclass(frozen=True)
class ChemicalFieldDefinition:
    key: str
    label: str
    unit: str
    description: str
    aliases: tuple[str, ...] = ()


CHEMICAL_FIELD_DEFINITIONS: tuple[ChemicalFieldDefinition, ...] = (
    ChemicalFieldDefinition("ec", "EC", "mS/cm", "電気伝導率", ("ec", "EC")),
    ChemicalFieldDefinition(
        "nh4n", "NH4-N", "mg/100g", "アンモニア態窒素", ("nh4n", "NH4-N")
    ),
    ChemicalFieldDefinition(
        "no3n", "NO3-N", "mg/100g", "硝酸態窒素", ("no3n", "NO3-N")
    ),
    ChemicalFieldDefinition(
        "total_nitrogen",
        "無機態N",
        "mg/100g",
        "無機態窒素（NH4+NO3）",
        ("total_nitrogen", "無機態N", "無機態窒素", "無機態窒素(NH4+NO3)"),
    ),
    ChemicalFieldDefinition(
        "nh4_per_nitrogen",
        "NH4/N比",
        "",
        "アンモニア態窒素比",
        ("nh4_per_nitrogen", "NH4/N比", "アンモニア態窒素比"),
    ),
    ChemicalFieldDefinition("ph", "pH", "", "水素イオン濃度", ("ph", "pH")),
    ChemicalFieldDefinition("cao", "CaO", "mg/100g", "交換性石灰", ("cao", "CaO")),
    ChemicalFieldDefinition("mgo", "MgO", "mg/100g", "交換性苦土", ("mgo", "MgO")),
    ChemicalFieldDefinition("k2o", "K2O", "mg/100g", "交換性加里", ("k2o", "K2O")),
    ChemicalFieldDefinition(
        "base_saturation",
        "塩基飽和度",
        "%",
        "塩基飽和度",
        ("base_saturation", "塩基飽和度"),
    ),
    ChemicalFieldDefinition(
        "cao_per_mgo", "CaO/MgO", "", "CaO/MgO比", ("cao_per_mgo", "CaO/MgO")
    ),
    ChemicalFieldDefinition(
        "mgo_per_k2o", "MgO/K2O", "", "MgO/K2O比", ("mgo_per_k2o", "MgO/K2O")
    ),
    ChemicalFieldDefinition(
        "phosphorus_absorption",
        "リン酸吸",
        "mg/100g",
        "リン酸吸収係数",
        ("phosphorus_absorption", "リン酸吸収係数", "リン酸吸"),
    ),
    ChemicalFieldDefinition(
        "p2o5", "P2O5", "mg/100g", "可給態リン酸", ("p2o5", "P2O5")
    ),
    ChemicalFieldDefinition("cec", "CEC", "meq/100g", "塩基置換容量", ("cec", "CEC")),
    ChemicalFieldDefinition("humus", "腐植", "%", "腐植", ("humus", "腐植")),
    ChemicalFieldDefinition(
        "bulk_density", "仮比重", "", "仮比重", ("bulk_density", "仮比重")
    ),
)

CHEMICAL_FIELD_KEYS: tuple[str, ...] = tuple(
    defn.key for defn in CHEMICAL_FIELD_DEFINITIONS
)


def normalize_text(value: str) -> str:
    """Excelの列名を正規化してマッチング用に整形する

    Excelファイル（特に川田研究所フォーマット）では、手入力やコピペによって
    全角・半角の表記ゆれが発生しやすい。この関数で文字列を統一して
    確実にマッチングできるようにする。

    正規化処理:
        1. NFKC正規化（互換文字を統一）
           - 全角英数字 → 半角英数字 (例: "ＥＣ" → "EC")
           - 全角ハイフン → 半角ハイフン (例: "NH4－N" → "NH4-N")
           - 全角カッコ → 半角カッコ (例: "（NH4+NO3）" → "(NH4+NO3)")
        2. 小文字化 (例: "EC" → "ec")
        3. 前後の空白除去
        4. スペース除去（半角・全角）
        5. カッコの統一（全角→半角）

    Args:
        value: 正規化対象の文字列（Excel列名など）

    Returns:
        正規化された文字列

    Examples:
        >>> normalize_text("NH4-N")
        'nh4-n'
        >>> normalize_text("NH4－N")  # 全角ハイフン
        'nh4-n'
        >>> normalize_text("ＥＣ")  # 全角英字
        'ec'
        >>> normalize_text("無機態窒素（NH4+NO3）")  # 全角カッコ
        '無機態窒素(nh4+no3)'
    """
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return (
        normalized.replace(" ", "")
        .replace("　", "")
        .replace("（", "(")
        .replace("）", ")")
    )


def build_alias_to_field_key_map() -> dict[str, str]:
    """正規化済みエイリアス → フィールドキーのマッピング辞書を生成する

    CHEMICAL_FIELD_DEFINITIONSに定義された全フィールドのエイリアスを
    normalize_text()で正規化し、対応するフィールドキーへのマッピングを作成する。
    この辞書を使うことで、Excelの列名から素早くフィールドを特定できる。

    Returns:
        正規化済みエイリアス -> フィールドキーの辞書

    Examples:
        >>> mapping = build_alias_to_field_key_map()
        >>> mapping["ec"]  # 小文字
        'ec'
        >>> mapping["nh4-n"]  # ハイフン付き
        'nh4n'
        >>> mapping["無機態窒素(nh4+no3)"]  # 日本語+英数字
        'total_nitrogen'
    """
    alias_map: dict[str, str] = {}
    for defn in CHEMICAL_FIELD_DEFINITIONS:
        for alias in (defn.key, *defn.aliases):
            alias_map[normalize_text(alias)] = defn.key
    return alias_map


CHEMICAL_FIELD_ALIAS_TO_KEY: dict[str, str] = build_alias_to_field_key_map()
