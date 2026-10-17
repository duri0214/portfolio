"""土壌分類に関するドメインサービス。"""

import re

from soil_analysis.domain.valueobject.soil_classification import (
    SOIL_GROUP_EXPLANATION_URLS,
    SOIL_GROUP_NAMES,
    SOIL_GROUP_SUMMARIES,
    SOIL_INVENTORY_URL,
)


class SoilClassificationService:
    """土壌コードと画面表示用の情報を変換する。"""

    @staticmethod
    def normalize_soil_name(name: str) -> str:
        """空の括弧を除いた画面表示用の土壌名を返す。"""
        normalized = str(name or "").strip()
        return re.sub(r"[（(]\s*[）)]", "", normalized)

    @staticmethod
    def get_soil_group_name(code: str) -> str:
        """土壌群コードに対応する名称を返す。"""
        return SOIL_GROUP_NAMES.get(code, code)

    @staticmethod
    def get_soil_group_url(code: str) -> str:
        """土壌群コードの解説ページURLを返す。"""
        return SOIL_GROUP_EXPLANATION_URLS.get(code, SOIL_INVENTORY_URL)

    @staticmethod
    def get_soil_group_summary(code: str) -> str:
        """土壌群コードの特徴概要を返す。"""
        return SOIL_GROUP_SUMMARIES.get(
            code,
            "この土壌群の分類と特性は、農研機構の解説ページで確認できます。",
        )
