from dataclasses import dataclass


@dataclass(frozen=True)
class ChemicalFieldDefinition:
    key: str
    label: str
    unit: str
    description: str
    aliases: tuple[str, ...] = ()


CHEMICAL_FIELD_DEFINITIONS: tuple[ChemicalFieldDefinition, ...] = (
    ChemicalFieldDefinition("ec", "EC", "mS/cm", "電気伝導率", ("ec", "EC")),
    ChemicalFieldDefinition("nh4n", "NH4-N", "mg/100g", "アンモニア態窒素", ("nh4-n", "nh4n")),
    ChemicalFieldDefinition("no3n", "NO3-N", "mg/100g", "硝酸態窒素", ("no3-n", "no3n")),
    ChemicalFieldDefinition("total_nitrogen", "無機態N", "mg/100g", "無機態窒素（NH4+NO3）"),
    ChemicalFieldDefinition("nh4_per_nitrogen", "NH4/N比", "", "アンモニア態窒素比"),
    ChemicalFieldDefinition("ph", "pH", "", "水素イオン濃度", ("ph", "pH")),
    ChemicalFieldDefinition("cao", "CaO", "mg/100g", "交換性石灰", ("cao", "CaO")),
    ChemicalFieldDefinition("mgo", "MgO", "mg/100g", "交換性苦土", ("mgo", "MgO")),
    ChemicalFieldDefinition("k2o", "K2O", "mg/100g", "交換性加里", ("k2o", "K2O")),
    ChemicalFieldDefinition("base_saturation", "塩基飽和度", "%", "塩基飽和度"),
    ChemicalFieldDefinition("cao_per_mgo", "CaO/MgO", "", "CaO/MgO比"),
    ChemicalFieldDefinition("mgo_per_k2o", "MgO/K2O", "", "MgO/K2O比"),
    ChemicalFieldDefinition(
        "phosphorus_absorption",
        "リン酸吸",
        "mg/100g",
        "リン酸吸収係数",
        ("リン酸吸", "リン酸吸収係数"),
    ),
    ChemicalFieldDefinition("p2o5", "P2O5", "mg/100g", "可給態リン酸", ("p2o5", "P2O5")),
    ChemicalFieldDefinition("cec", "CEC", "meq/100g", "塩基置換容量", ("cec", "CEC")),
    ChemicalFieldDefinition("humus", "腐植", "%", "腐植"),
    ChemicalFieldDefinition("bulk_density", "仮比重", "", "仮比重"),
)

CHEMICAL_FIELD_KEYS: tuple[str, ...] = tuple(defn.key for defn in CHEMICAL_FIELD_DEFINITIONS)


def build_alias_to_field_key_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for defn in CHEMICAL_FIELD_DEFINITIONS:
        for alias in (defn.key, *defn.aliases):
            alias_map[alias.strip().lower()] = defn.key
    return alias_map


CHEMICAL_FIELD_ALIAS_TO_KEY: dict[str, str] = build_alias_to_field_key_map()


def resolve_chemical_field_key(column_name: str) -> str | None:
    normalized = column_name.strip().lower()
    return CHEMICAL_FIELD_ALIAS_TO_KEY.get(normalized)
