from soil_analysis.domain.dataprovider.land_review_comment_generator import (
    LandReviewCommentGenerator,
)
from soil_analysis.domain.repository.chemical_measurement import (
    SoilChemicalMeasurementRepository,
)
from soil_analysis.domain.repository.hardness_measurement import (
    SoilHardnessMeasurementRepository,
)
from soil_analysis.models import LandLedger


class LandReviewCommentGenerationService:
    """台帳に取り込まれた測定種別を材料にGPT評価コメントの下書きを作る。"""

    @staticmethod
    def generate(land_ledger: LandLedger) -> str:
        """硬度・化学分析の取込状況だけを渡し、保存前のコメント下書きを返す。"""
        has_chemical_analysis = (
            SoilChemicalMeasurementRepository.get_by_ledger(land_ledger) is not None
        )
        has_hardness_measurement = SoilHardnessMeasurementRepository.has_measurements(
            land_ledger
        )
        chemical_status = "取り込み済み" if has_chemical_analysis else "未取り込み"
        hardness_status = "取り込み済み" if has_hardness_measurement else "未取り込み"
        prompt = f"""次の台帳について、通知表に載せる評価コメントの下書きを日本語で作成してください。

- 化学分析: {chemical_status}
- 土壌硬度: {hardness_status}

数値や未提供の事実を推測せず、取り込み済みの測定は通知表で確認するよう促してください。未取り込みの測定は、確認後に評価を補う必要があると簡潔に示してください。200文字程度、改行を使って読みやすくしてください。"""
        return LandReviewCommentGenerator().generate(prompt)
