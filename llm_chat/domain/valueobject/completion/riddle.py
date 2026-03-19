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


class RiddleEvaluation(BaseModel):
    """
    なぞなぞセッション全体の総合評価結果（集約された最終評価）。

    複数のなぞなぞ（Riddle）の出題・回答セッションがすべて終了した後に、
    「正確性」や「論理」などの各観点を多角的に分析し、セッション全体を通じた
    最終的な能力判定を保持します。

    各属性は個別の「評価観点」であり、それらを合算した `total_score` が、
    セッション全体を通じたユーザーの最終的なパフォーマンス指標となります。

    Attributes:
        correctness (int): 正確性の評価観点 (0-5)。各問題の回答の正確さが蓄積・反映されます。
        reasoning (int): 論理的思考の評価観点 (0-5)。回答に至るプロセスや筋道の通りやすさを評価します。
        creativity (int): 独創性の評価観点 (0-5)。ユニークな視点や、型にはまらない発想を評価します。
        rebuttal (int): 反論力の評価観点 (0-5)。AIからの指摘に対する反応や、自説の補強能力を評価します。
        comment (str): 各観点の評価に基づいた、セッション全体の総評・アドバイス。
    """

    correctness: int = Field(..., ge=0, le=5, description="正確性 (0-5)")
    reasoning: int = Field(..., ge=0, le=5, description="論理 (0-5)")
    creativity: int = Field(..., ge=0, le=5, description="独創性 (0-5)")
    rebuttal: int = Field(..., ge=0, le=5, description="反論 (0-5)")
    comment: str = Field(..., description="コメント")

    @property
    def total_score(self) -> int:
        """
        セッションを通じた総合スコアを算出します。

        このモデルでは固定の「満点（最大合計値）」は定義していません。
        各項目の加算結果が最終的なスコアとして扱われます。
        """
        return self.correctness + self.reasoning + self.creativity + self.rebuttal


class RiddleTurnEvaluation(BaseModel):
    """
    なぞなぞの単問評価結果。

    1問ごとの回答内容に対して、各観点を数値化します。
    """

    correctness: int = Field(..., ge=0, le=5, description="正確性 (0-5)")
    reasoning: int = Field(..., ge=0, le=5, description="論理 (0-5)")
    creativity: int = Field(..., ge=0, le=5, description="独創性 (0-5)")
    rebuttal: int = Field(..., ge=0, le=5, description="反論 (0-5)")


class SessionState(Enum):
    """
    なぞなぞセッションの状態。

    Attributes:
        START (str): 開始
        USER_INPUT (str): 入力受領（回答待ち）
        EVALUATE (str): 評価中
        FINISHED (str): 終了
    """

    START = "START"
    USER_INPUT = "USER_INPUT"
    EVALUATE = "EVALUATE"
    FINISHED = "FINISHED"

    @property
    def next_state(self) -> "SessionState":
        """
        現在のフェーズの「次」の状態を返します。

        このメソッドは、なぞなぞセッションの標準的な進行（START -> USER_INPUT -> EVALUATE -> USER_INPUT ...）
        における論理的な次のステップを定義します。

        Returns:
            SessionState: 次に遷移すべき状態。
                - FINISHED 状態の場合は FINISHED を維持します。
                - 未定義の遷移（transitions にない場合）は自分自身を返します。
        """
        if self == SessionState.FINISHED:
            return SessionState.FINISHED

        transitions: dict["SessionState", "SessionState"] = {
            SessionState.START: SessionState.USER_INPUT,
            SessionState.USER_INPUT: SessionState.EVALUATE,
            SessionState.EVALUATE: SessionState.USER_INPUT,
        }
        return transitions.get(self, self)

    @classmethod
    def from_csv(cls, next_riddle_state: str) -> list["SessionState"]:
        """
        保存された next_riddle_state（カンマ区切りの履歴）から SessionState のリストを復元します。
        """
        if not next_riddle_state:
            return []
        states = []
        for s in next_riddle_state.split(","):
            s = s.strip()
            if not s:
                continue
            try:
                # 削除された WAIT_ANSWER や古い UserInput を USER_INPUT にマッピングする
                if s == "WAIT_ANSWER" or s == "UserInput":
                    states.append(cls.USER_INPUT)
                    continue
                states.append(cls(s))
            except ValueError:
                continue
        return states

    @staticmethod
    def to_csv(states: list["SessionState"] | None) -> str:
        """
        SessionState のリストをカンマ区切りの文字列に変換します。
        """
        if not states:
            return ""
        return ",".join(s.value for s in states)


@dataclass
class RiddleSession:
    """
    なぞなぞセッションのドメインモデル。

    「問題 → 回答 → 評価 → 反論 → 再評価」という一連の流れを管理します。

    Attributes:
        riddles (list[Riddle]): 出題されるなぞなぞのリスト。
        answers (list[str]): ユーザーからの回答履歴。
        evaluations (list[RiddleEvaluation]): 各ターンの評価結果。
        rebuttals (list[str]): ユーザーからの反論履歴。
        state (SessionState): セッションの現在状態。
        current_index (int): 現在何問目か（0から開始）。
    """

    riddles: list[Riddle]
    answers: list[str] = field(default_factory=list)
    evaluations: list[RiddleEvaluation] = field(default_factory=list)
    rebuttals: list[str] = field(default_factory=list)
    state: SessionState = SessionState.START
    current_index: int = 0


class GenderType(Enum):
    """
    性別の列挙型。

    Attributes:
        MAN (str): 男性
        WOMAN (str): 女性
    """

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
        評価結果を Markdown 形式の箇条書きテキストに変換します。

        フロントエンドでの表示を考慮し、セクションの区切りに空行を挿入することで
        Markdown パーサーが正しくリストとして解釈できるように構成します。
        """
        lines = ["", "### 【評価結果】"]
        if self.evaluation:
            lines.append(f"- **正確性**: {self.evaluation.correctness}/5")
            lines.append(f"- **論理性**: {self.evaluation.reasoning}/5")
            lines.append(f"- **独創性**: {self.evaluation.creativity}/5")
            lines.append(f"- **反論力**: {self.evaluation.rebuttal}/5")
            lines.append(f"- **合計スコア**: {self.evaluation.total_score}")
            lines.append(f"- **コメント**: {self.evaluation.comment}")
        else:
            lines.append("- 評価データがありません。")
        return "\n".join(lines)
