from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from lib.llm.valueobject.completion import ChatResult


class GenderType(Enum):
    MAN = "man"
    WOMAN = "woman"


@dataclass
class Gender:
    gender: GenderType

    @property
    def name(self) -> str:
        return "男性" if self.gender == GenderType.MAN else "女性"


class RiddleEvaluation(BaseModel):
    """
    なぞなぞの各評価観点（論理的思考力、洞察力など）に対する個別の評価結果を表す。

    RiddleResponse の evaluations リストの要素として使用される、最小単位の評価データ（観点別評価）。

    Attributes:
        viewpoint (str): 評価観点名（例: 論理的思考力、洞察力）。
        score (int): 評価スコア（0-100）。
        judge (str): 判定結果（例: 合格、不合格）。
    """

    viewpoint: str = Field(..., description="評価観点名（例: 論理的思考力、洞察力）")
    score: int = Field(..., description="評価スコア（0-100）")
    judge: str = Field(..., description="判定結果（例: 合格、不合格）")


class RiddleResponse(ChatResult):
    """
    なぞなぞタスクの最終的な構造化レスポンス（集約ルート）。

    BaseModelである ChatResult を継承し、複数の RiddleEvaluation をリスト形式で保持する。
    処理の流れとして、LLMから返されたJSONをパースしてこのクラスにマッピングすることで、
    型安全な評価結果の提供を保証する。

    Attributes:
        answer (str): LLMから返された生の回答テキスト。
        explanation (str | None): 評価に関する補足説明。
        metadata (dict[str, Any]): トークン数やモデル名などの付随情報。
        evaluations (list[RiddleEvaluation]): 各評価観点（viewpoint）ごとの評価詳細リスト。
    """

    evaluations: list[RiddleEvaluation] = Field(
        ..., description="各評価観点ごとの評価リスト"
    )

    def to_bullet_points(self) -> str:
        """
        評価結果を箇条書き形式のテキストに変換します。
        """
        lines = ["\n【評価結果】"]
        for eval_item in self.evaluations:
            lines.append(
                f"- {eval_item.viewpoint}: {eval_item.score}点 ({eval_item.judge})"
            )
        return "\n".join(lines)
