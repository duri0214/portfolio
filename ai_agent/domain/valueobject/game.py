from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from ai_agent.domain.valueobject.agent_execution import AgentRun
from ai_agent.domain.valueobject.skill_tool import SkillCategory


@dataclass(frozen=True)
class Position:
    """盤面上のマスを表す値オブジェクト。

    Attributes:
        row: 0以上の行番号。
        column: 0以上の列番号。
    """

    row: int
    column: int

    def __post_init__(self) -> None:
        if self.row < 0 or self.column < 0:
            raise ValueError("position coordinates must be non-negative")


class BoardSpaceType(StrEnum):
    """問題以外の盤面マスが持つゲーム上の役割。"""

    EXPERIENCE_BONUS = "experience_bonus"
    REST = "rest"

    @property
    def display_name(self) -> str:
        """盤面と履歴に表示する役割名を返す。"""
        return {
            BoardSpaceType.EXPERIENCE_BONUS: "経験値ボーナス",
            BoardSpaceType.REST: "休憩",
        }[self]


@dataclass(frozen=True)
class BoardSpace:
    """問題マス以外の盤面マスと、その一度だけの効果を表す値。"""

    space_id: str
    name: str
    space_type: BoardSpaceType
    position: Position
    effect_description: str

    def __post_init__(self) -> None:
        if not self.space_id or not self.name or not self.effect_description:
            raise ValueError("board space metadata must not be empty")
        try:
            space_type = BoardSpaceType(self.space_type)
        except (TypeError, ValueError) as error:
            raise ValueError("unknown board space type") from error
        object.__setattr__(self, "space_type", space_type)

    @property
    def type_display_name(self) -> str:
        """画面表示用の盤面マスの役割名を返す。"""
        return self.space_type.display_name


@dataclass(frozen=True)
class MondaiState:
    """盤面上の問題駒と解答状態を表す値オブジェクト。

    Attributes:
        mondai_id: AgentやUIが参照する安定した問題識別子。
        name: 画面に表示する問題名。
        category: 問題の主教科。
        position: 盤面上の位置。
        hit_points: 問題の残りHP。0なら解決済み。
        related_category: 科目横断問題の関連教科。
    """

    mondai_id: str
    name: str
    category: SkillCategory
    position: Position
    hit_points: int = 3
    related_category: SkillCategory | None = None

    def __post_init__(self) -> None:
        if not self.mondai_id or not self.name:
            raise ValueError("mondai_id and name must not be empty")
        if self.hit_points < 0:
            raise ValueError("hit_points must not be negative")

    @property
    def solved(self) -> bool:
        """問題が解決済みかどうかを返す。"""
        return self.hit_points == 0

    @property
    def categories(self) -> tuple[SkillCategory, ...]:
        """問題に関連する教科を重複なく返す。"""
        if self.related_category is None or self.related_category == self.category:
            return (self.category,)
        return (self.category, self.related_category)

    @property
    def category_display_name(self) -> str:
        """問題の教科を画面表示用の名前で返す。"""
        return " × ".join(category.display_name for category in self.categories)


@dataclass(frozen=True)
class PresetLine:
    """プレイヤーがAgentへ渡せるプリセットセリフ。

    Attributes:
        line_id: セリフの識別子。
        label: 選択肢として表示する意図の名前。
        text: 画面に表示するセリフ本文。
        description: Agentに伝える意図の説明。
    """

    line_id: str
    label: str
    text: str
    description: str


@dataclass(frozen=True)
class ToolExecutionRecord:
    """画面に表示するSkill 1回分の実行記録。"""

    sequence: int
    tool_name: str
    display_name: str
    operation: str
    target_problem_name: str
    input_summary: str
    success: bool
    result_summary: str
    power: int
    damage: int
    experience_gained: int
    remaining_hit_points: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ToolExecutionRecord:
        """保存済み状態の辞書から実行記録を復元する。"""
        return cls(
            sequence=int(value.get("sequence", 0)),
            tool_name=str(value.get("tool_name", "")),
            display_name=str(value.get("display_name", "")),
            operation=str(value.get("operation", "")),
            target_problem_name=str(value.get("target_problem_name", "")),
            input_summary=str(value.get("input_summary", "")),
            success=bool(value.get("success", False)),
            result_summary=str(value.get("result_summary", "")),
            power=int(value.get("power", value.get("damage", 0))),
            damage=int(value.get("damage", 0)),
            experience_gained=int(value.get("experience_gained", 0)),
            remaining_hit_points=int(value.get("remaining_hit_points", 0)),
        )


@dataclass(frozen=True)
class AgentExecutionRecord:
    """画面に表示するAgent 1回分の実行記録。"""

    run_id: str
    problem_id: str
    problem_name: str
    problem_subjects: str
    line_label: str
    line_text: str
    status: str
    explanation: str
    steps: tuple[ToolExecutionRecord, ...]
    error: str | None = None
    agent_run: AgentRun | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AgentExecutionRecord:
        """保存済み状態の辞書からAgent実行記録を復元する。"""
        return cls(
            run_id=str(value.get("run_id", "")),
            problem_id=str(value.get("problem_id", "")),
            problem_name=str(value.get("problem_name", "")),
            problem_subjects=str(value.get("problem_subjects", "")),
            line_label=str(value.get("line_label", "")),
            line_text=str(value.get("line_text", "")),
            status=str(value.get("status", "")),
            explanation=str(value.get("explanation", "")),
            steps=tuple(
                ToolExecutionRecord.from_dict(step)
                for step in value.get("steps", ())
                if isinstance(step, dict)
            ),
            error=(str(value["error"]) if value.get("error") else None),
            agent_run=(
                AgentRun.from_dict(value["agent_run"])
                if isinstance(value.get("agent_run"), dict)
                else None
            ),
        )


@dataclass(frozen=True)
class BoardEventRecord:
    """盤面イベントの移動結果を画面履歴へ保存する値。"""

    space_id: str
    space_name: str
    space_type: str
    summary: str
    experience_gained: int
    recovered_hit_points: int
    recovered_problem_count: int

    @property
    def space_type_display_name(self) -> str:
        """履歴に表示する盤面マスの役割名を返す。"""
        try:
            return BoardSpaceType(self.space_type).display_name
        except ValueError:
            return self.space_type

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BoardEventRecord:
        """署名付きCookieまたはセッションの辞書から履歴を復元する。"""
        return cls(
            space_id=str(value.get("space_id", "")),
            space_name=str(value.get("space_name", "")),
            space_type=str(value.get("space_type", "")),
            summary=str(value.get("summary", "")),
            experience_gained=int(value.get("experience_gained", 0)),
            recovered_hit_points=int(value.get("recovered_hit_points", 0)),
            recovered_problem_count=int(value.get("recovered_problem_count", 0)),
        )


@dataclass(frozen=True)
class GameState:
    """プレイヤー、問題駒、選択状態をまとめたゲームスナップショット。

    Attributes:
        board_size: 正方形盤面の一辺のマス数。
        player_position: プレイヤー駒の位置。
        experience: プレイヤーが獲得した経験値。
        mondais: 単一教科または科目横断の6つの問題駒。
        board_spaces: 問題以外の2つの盤面マス。
        preset_lines: プレイヤーが選択できるプリセットセリフ。
        selected_mondai_id: 現在選択中の問題識別子。
        selected_line_id: 現在選択中のセリフ識別子。
        tool_history: Agentが実行したTool名の履歴。
        execution_history: Agentの判断とSkill結果を含む実行履歴。
        used_board_space_ids: 効果を使い終えた盤面マスの識別子。
        board_event_history: 盤面イベントの移動結果を新しい順で並べた履歴。
    """

    board_size: int
    player_position: Position
    experience: int
    mondais: tuple[MondaiState, ...]
    preset_lines: tuple[PresetLine, ...]
    selected_mondai_id: str | None = None
    selected_line_id: str | None = None
    tool_history: tuple[str, ...] = ()
    execution_history: tuple[AgentExecutionRecord, ...] = ()
    used_board_space_ids: tuple[str, ...] = ()
    board_event_history: tuple[BoardEventRecord, ...] = ()
    board_spaces: tuple[BoardSpace, ...] = ()

    def __post_init__(self) -> None:
        if self.board_size < 1:
            raise ValueError("board_size must be greater than zero")
        if self.experience < 0:
            raise ValueError("experience must not be negative")
        if len(self.mondais) != 6:
            raise ValueError("a game must contain exactly six problems")
        if any(
            mondai.position.row >= self.board_size
            or mondai.position.column >= self.board_size
            for mondai in self.mondais
        ):
            raise ValueError("mondai position must be inside the board")
        if not self.board_spaces and self.board_size == 3:
            object.__setattr__(self, "board_spaces", self._default_board_spaces())
        if any(
            space.position.row >= self.board_size
            or space.position.column >= self.board_size
            for space in self.board_spaces
        ):
            raise ValueError("board space position must be inside the board")
        if len({space.space_id for space in self.board_spaces}) != len(
            self.board_spaces
        ):
            raise ValueError("board space identifiers must be unique")
        problem_positions = {mondai.position for mondai in self.mondais}
        if any(space.position in problem_positions for space in self.board_spaces):
            raise ValueError("board space cannot share a problem position")

    @staticmethod
    def _default_board_spaces() -> tuple[BoardSpace, ...]:
        """3x3盤面の空き2マスに配置するイベントマスを返す。"""
        return (
            BoardSpace(
                "board-space-bonus",
                "経験値ボーナス",
                BoardSpaceType.EXPERIENCE_BONUS,
                Position(1, 2),
                "初回の移動で経験値を10獲得する",
            ),
            BoardSpace(
                "board-space-rest",
                "休憩",
                BoardSpaceType.REST,
                Position(2, 0),
                "初回の移動で未解決の問題を1HP回復する",
            ),
        )

    @classmethod
    def initial(cls) -> GameState:
        """3x3盤面と問題・イベントマスを作成する。"""
        return cls(
            board_size=3,
            player_position=Position(1, 1),
            experience=0,
            mondais=(
                MondaiState(
                    "mondai-language",
                    "国語の問題",
                    SkillCategory.LANGUAGE,
                    Position(0, 0),
                ),
                MondaiState(
                    "mondai-language-mathematics",
                    "国語×算数の問題",
                    SkillCategory.LANGUAGE,
                    Position(0, 1),
                    related_category=SkillCategory.MATHEMATICS,
                ),
                MondaiState(
                    "mondai-mathematics",
                    "算数の問題",
                    SkillCategory.MATHEMATICS,
                    Position(0, 2),
                ),
                MondaiState(
                    "mondai-language-science",
                    "国語×理科の問題",
                    SkillCategory.LANGUAGE,
                    Position(1, 0),
                    related_category=SkillCategory.SCIENCE,
                ),
                MondaiState(
                    "mondai-mathematics-science",
                    "算数×理科の問題",
                    SkillCategory.MATHEMATICS,
                    Position(2, 1),
                    related_category=SkillCategory.SCIENCE,
                ),
                MondaiState(
                    "mondai-science",
                    "理科の問題",
                    SkillCategory.SCIENCE,
                    Position(2, 2),
                ),
            ),
            board_spaces=cls._default_board_spaces(),
            preset_lines=(
                PresetLine(
                    "line-challenge",
                    "直接解決を試す",
                    "まず答えを出してみる。",
                    "直接使えそうなSkillから始め、結果に応じて必要なら別のSkillも続ける。",
                ),
                PresetLine(
                    "line-observe",
                    "条件を整理して解く",
                    "問題文の条件を整理してから解く。",
                    "問題文や観察結果を分析し、足りない処理があれば次のSkillへつなげる。",
                ),
                PresetLine(
                    "line-chain",
                    "別の観点で検証する",
                    "別の見方も使って答えを確かめる。",
                    "複数の観点を試し、Skillの結果を次のSkill選択に活かす。",
                ),
            ),
        )

    def with_selection(
        self, *, mondai_id: str | None = None, line_id: str | None = None
    ) -> GameState:
        """選択状態だけを更新した新しいスナップショットを返す。"""
        return replace(
            self,
            selected_mondai_id=(
                mondai_id if mondai_id is not None else self.selected_mondai_id
            ),
            selected_line_id=line_id if line_id is not None else self.selected_line_id,
        )

    def mondai(self, mondai_id: str) -> MondaiState:
        """指定した問題駒を返す。"""
        return next(mondai for mondai in self.mondais if mondai.mondai_id == mondai_id)

    def board_space(self, space_id: str) -> BoardSpace:
        """指定したイベントマスを返す。"""
        return next(space for space in self.board_spaces if space.space_id == space_id)

    def with_execution_record(self, record: AgentExecutionRecord) -> GameState:
        """Agent実行記録を最新順で追加した状態を返す。"""
        return replace(self, execution_history=(record,) + self.execution_history)

    def to_dict(self) -> dict[str, Any]:
        """Djangoセッションへ保存するゲーム状態の辞書を返す。"""
        return json.loads(
            json.dumps(asdict(self), ensure_ascii=False, default=_json_default)
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GameState:
        """Djangoセッションの辞書からゲーム状態を復元する。"""
        if not isinstance(value, dict):
            raise TypeError("game state must be a dictionary")

        initial = cls.initial()
        mondai_payload = value.get("mondais", ())
        if not isinstance(mondai_payload, (list, tuple)):
            raise TypeError("mondais must be a list or tuple")
        health_by_mondai = {
            mondai["mondai_id"]: int(mondai["hit_points"])
            for mondai in mondai_payload
            if isinstance(mondai, dict)
            and "mondai_id" in mondai
            and "hit_points" in mondai
        }
        mondais = tuple(
            replace(
                mondai,
                hit_points=health_by_mondai.get(mondai.mondai_id, mondai.hit_points),
            )
            for mondai in initial.mondais
        )
        player_position_payload = value.get("player_position", {})
        if not isinstance(player_position_payload, dict):
            raise TypeError("player_position must be a dictionary")
        player_position = Position(
            int(player_position_payload.get("row", initial.player_position.row)),
            int(player_position_payload.get("column", initial.player_position.column)),
        )
        selected_mondai_id = value.get("selected_mondai_id")
        selected_line_id = value.get("selected_line_id")
        if selected_mondai_id is not None and not isinstance(selected_mondai_id, str):
            raise TypeError("selected_mondai_id must be a string or None")
        if selected_line_id is not None and not isinstance(selected_line_id, str):
            raise TypeError("selected_line_id must be a string or None")

        tool_history = value.get("tool_history", ())
        execution_history = value.get("execution_history", ())
        used_board_space_ids = value.get("used_board_space_ids", ())
        board_event_history = value.get("board_event_history", ())
        for field_name, field_value in (
            ("tool_history", tool_history),
            ("execution_history", execution_history),
            ("used_board_space_ids", used_board_space_ids),
            ("board_event_history", board_event_history),
        ):
            if not isinstance(field_value, (list, tuple)):
                raise TypeError(f"{field_name} must be a list or tuple")

        return replace(
            initial,
            player_position=player_position,
            experience=int(value.get("experience", 0)),
            mondais=mondais,
            selected_mondai_id=selected_mondai_id,
            selected_line_id=selected_line_id,
            tool_history=tuple(str(tool_name) for tool_name in tool_history),
            execution_history=tuple(
                AgentExecutionRecord.from_dict(record)
                for record in execution_history
                if isinstance(record, dict)
            ),
            used_board_space_ids=tuple(
                str(space_id) for space_id in used_board_space_ids
            ),
            board_event_history=tuple(
                BoardEventRecord.from_dict(record)
                for record in board_event_history
                if isinstance(record, dict)
            ),
        )


def _json_default(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")
