from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field

from lib.llm.valueobject.completion import ChatResult


@dataclass
class Riddle:
    """
    なぞなぞのドメインモデル。

    出題データ（マスターデータ）と、評価・分析に必要な
    「評価タグ（メタデータ）」を保持するドメインオブジェクトです。

    Attributes:
        question (str): なぞなぞの問題文。
        answer (str): なぞなぞの想定される正解（模範解答）。
        evaluation_tags (list[str]): 評価時に考慮すべきタグ（例: "論理的", "言葉遊び", "知識" など）。
    """

    question: str
    answer: str
    evaluation_tags: list[str] = field(default_factory=list)


class GenderType(Enum):
    MAN = "man"
    WOMAN = "woman"


@dataclass
class Gender:
    """
    ユーザーの性別を表現する値オブジェクト。

    Attributes:
        gender (GenderType): 性別の列挙型。
    """

    gender: GenderType

    @property
    def name(self) -> str:
        """
        性別の日本語名を返します。
        """
        return "男性" if self.gender == GenderType.MAN else "女性"


class RiddleEvaluation(BaseModel):
    """
    なぞなぞセッション全体の総合評価結果。

    複数のなぞなぞ（Riddle）の出題・回答セッションがすべて終了した後に、
    それまでの各回答に対する「正解度」や「考え方」などが、セッション全体を通じて
    蓄積・加算された最終的な評価結果を保持します。
    単一の問題に対する評価ではなく、全問を通じた総合的な能力判定です。

    Attributes:
        correctness (int): 正確性の総合点 (0-5)。各問題の正解状況が加算・反映されます。
        reasoning (int): 論理的思考の総合点 (0-5)。回答に至るプロセスが評価されます。
        creativity (int): 独創性の総合点 (0-5)。ユニークな視点や発想が評価されます。
        rebuttal (int): 反論力の総合点 (0-3)。AIの指摘に対する反応などが評価されます。
        comment (str): セッション全体を通じた総評・講評。
    """

    correctness: int = Field(..., ge=0, le=5, description="正確性 (0-5)")
    reasoning: int = Field(..., ge=0, le=5, description="論理 (0-5)")
    creativity: int = Field(..., ge=0, le=5, description="独創性 (0-5)")
    rebuttal: int = Field(..., ge=0, le=3, description="反論 (0-3)")
    comment: str = Field(..., description="コメント")

    @property
    def total_score(self) -> int:
        """スコアの合計計算はコード側で行われる"""
        return self.correctness + self.reasoning + self.creativity + self.rebuttal


class RiddleResponse(ChatResult):
    """
    なぞなぞタスクの最終的な構造化レスポンス（集約ルート）。

    BaseModelである ChatResult を継承し、セッション全体の評価結果（RiddleEvaluation）を保持します。
    処理の流れとして、全問終了後にLLMから返された評価JSONをパースしてこのクラスにマッピングすることで、
    型安全な総合評価の提供を保証します。

    Attributes:
        answer (str): LLMから返された生の回答テキスト。
        explanation (str | None): 評価に関する補足説明。
        metadata (dict[str, Any]): トークン数やモデル名などの付随情報。
        evaluation (RiddleEvaluation): セッション全体の総合評価詳細。
    """

    evaluation: RiddleEvaluation | None = Field(None, description="評価詳細")

    def to_bullet_points(self) -> str:
        """
        評価結果を箇条書き形式のテキストに変換します。
        """
        lines = ["\n【評価結果】"]
        if self.evaluation:
            lines.append(f"- 正確性: {self.evaluation.correctness}/5")
            lines.append(f"- 論理性: {self.evaluation.reasoning}/5")
            lines.append(f"- 独創性: {self.evaluation.creativity}/5")
            lines.append(f"- 反論力: {self.evaluation.rebuttal}/3")
            lines.append(f"- 合計スコア: {self.evaluation.total_score}")
            lines.append(f"- コメント: {self.evaluation.comment}")
        else:
            lines.append("- 評価データがありません。")
        return "\n".join(lines)
