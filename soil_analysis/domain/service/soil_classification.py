"""全国土壌図の土壌群コードを、画面で読める名称へ変換する。"""

import re

SOIL_INVENTORY_URL = "https://soil-inventory.rad.naro.go.jp/main/figure"

# 縮尺20万分の1土壌図で用いる土壌群コード。名称と分類の一次情報は
# 農研機構「日本土壌インベントリー」の分類表示に合わせる。
SOIL_GROUP_NAMES = {
    "A1": "人工物質土",
    "A2": "低地盛土造成土",
    "B1": "泥炭土",
    "C1": "ポドゾル",
    "D1": "未熟黒ボク土",
    "D2": "グライ黒ボク土",
    "D3": "多湿黒ボク土",
    "D4": "褐色黒ボク土",
    "D5": "非アロフェン質黒ボク土",
    "D6": "アロフェン質黒ボク土",
    "E1": "石灰性暗赤色土",
    "E2": "酸性暗赤色土",
    "E3": "塩基性暗赤色土",
    "F1": "低地水田土",
    "F2": "グライ低地土",
    "F3": "灰色低地土",
    "F4": "褐色低地土",
    "F5": "未熟低地土",
    "G": "赤黄色土",
    "G_": "赤黄色土",
    "G1": "粘土集積赤黄色土",
    "G2": "風化変質赤黄色土",
    "H1": "停滞水グライ土",
    "H2": "疑似グライ土",
    "I1": "褐色森林土",
    "J1": "火山放出物未熟土",
    "J2": "砂質未熟土",
    "J3": "固結岩屑土",
    "J4": "陸成未熟土",
    "Z1": "岩石地",
    "Z3": "市街地／水域など",
    "Z4": "鉱さい等採取地",
}

SOIL_GROUP_EXPLANATION_URLS = {
    code: f"https://soil-inventory.rad.naro.go.jp/explain/{code}.html"
    for code in SOIL_GROUP_NAMES
    if code not in {"A1", "A2", "G", "G_", "Z1", "Z3", "Z4"}
}

SOIL_GROUP_SUMMARIES = {
    "D2": "湿りやすい黒ボク土で、水分環境の違いを確認する手掛かりになります。",
    "D6": "火山灰を母材とし、アロフェンなどの粘土鉱物と腐植の集積が特徴の黒ボク土です。",
    "F2": "地下水位が高い低地に分布し、排水不良になりやすい土壌です。",
    "Z3": "市街地や水域などを表す区分で、栽培上の土壌特性を読む対象ではありません。",
}


def normalize_soil_name(name: str) -> str:
    """空の括弧が混ざった配布データの土壌名を画面表示用に整える。"""
    normalized = str(name or "").strip()
    return re.sub(r"[（(]\s*[）)]", "", normalized)


def get_soil_group_name(code: str) -> str:
    """土壌群コードに対応する名称を返し、未登録コードはコードをそのまま返す。"""
    return SOIL_GROUP_NAMES.get(code, code)


def get_soil_group_url(code: str) -> str:
    """土壌群の農研機構解説ページを返す。個別解説がない区分は分類一覧へ誘導する。"""
    return SOIL_GROUP_EXPLANATION_URLS.get(code, SOIL_INVENTORY_URL)


def get_soil_group_summary(code: str) -> str:
    """土壌群の特徴を短く返す。詳細は農研機構の解説ページで確認する。"""
    return SOIL_GROUP_SUMMARIES.get(
        code,
        "この土壌群の分布と性質は、農研機構の解説ページで確認できます。",
    )
