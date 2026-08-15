from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass, replace
import json

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


@dataclass(frozen=True)
class EnemyState:
    """盤面上の敵駒と戦闘状態を表す値オブジェクト。

    Attributes:
        enemy_id: AgentやUIが参照する安定した敵識別子。
        name: 画面に表示する敵名。
        category: 敵に対応する教科。
        position: 盤面上の位置。
        hit_points: 残り体力。0なら撃破済み。
    """

    enemy_id: str
    name: str
    category: SkillCategory
    position: Position
    hit_points: int = 3

    def __post_init__(self) -> None:
        if not self.enemy_id or not self.name:
            raise ValueError("enemy_id and name must not be empty")
        if self.hit_points < 0:
            raise ValueError("hit_points must not be negative")

    @property
    def defeated(self) -> bool:
        """敵の体力が0以下かどうかを返す。"""
        return self.hit_points == 0


@dataclass(frozen=True)
class PresetLine:
    """プレイヤーがAgentへ渡せるプリセットセリフ。

    Attributes:
        line_id: セリフの識別子。
        text: 画面に表示するセリフ本文。
    """

    line_id: str
    text: str


@dataclass(frozen=True)
class GameState:
    """プレイヤー、敵駒、選択状態をまとめたゲームスナップショット。

    Attributes:
        board_size: 正方形盤面の一辺のマス数。
        player_position: プレイヤー駒の位置。
        experience: プレイヤーが獲得した経験値。
        enemies: 3体の敵駒。
        preset_lines: プレイヤーが選択できるプリセットセリフ。
        selected_enemy_id: 現在選択中の敵識別子。
        selected_line_id: 現在選択中のセリフ識別子。
        tool_history: Agentが実行したTool名の履歴。
    """

    board_size: int
    player_position: Position
    experience: int
    enemies: tuple[EnemyState, ...]
    preset_lines: tuple[PresetLine, ...]
    selected_enemy_id: str | None = None
    selected_line_id: str | None = None
    tool_history: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.board_size < 1:
            raise ValueError("board_size must be greater than zero")
        if self.experience < 0:
            raise ValueError("experience must not be negative")
        if len(self.enemies) != 3:
            raise ValueError("a game must contain exactly three enemies")
        if any(
            enemy.position.row >= self.board_size
            or enemy.position.column >= self.board_size
            for enemy in self.enemies
        ):
            raise ValueError("enemy position must be inside the board")

    @classmethod
    def initial(cls) -> GameState:
        """3x3盤面と国語・算数・理科の敵駒を作成する。"""
        return cls(
            board_size=3,
            player_position=Position(1, 1),
            experience=0,
            enemies=(
                EnemyState(
                    "enemy-language",
                    "国語の問題",
                    SkillCategory.LANGUAGE,
                    Position(0, 0),
                ),
                EnemyState(
                    "enemy-mathematics",
                    "算数の問題",
                    SkillCategory.MATHEMATICS,
                    Position(0, 2),
                ),
                EnemyState(
                    "enemy-science", "理科の問題", SkillCategory.SCIENCE, Position(2, 2)
                ),
            ),
            preset_lines=(
                PresetLine("line-challenge", "この問題を解いてみせる！"),
                PresetLine("line-observe", "よく観察して答えを導く。"),
                PresetLine("line-chain", "別のSkillも組み合わせて突破する！"),
            ),
        )

    def with_selection(
        self, *, enemy_id: str | None = None, line_id: str | None = None
    ) -> GameState:
        """選択状態だけを更新した新しいスナップショットを返す。"""
        return replace(
            self,
            selected_enemy_id=(
                enemy_id if enemy_id is not None else self.selected_enemy_id
            ),
            selected_line_id=line_id if line_id is not None else self.selected_line_id,
        )

    def enemy(self, enemy_id: str) -> EnemyState:
        """指定した敵駒を返す。"""
        return next(enemy for enemy in self.enemies if enemy.enemy_id == enemy_id)

    def to_json(self) -> str:
        """ブラウザへ署名付きCookieとして保存できるJSONを返す。"""
        return json.dumps(asdict(self), ensure_ascii=True)

    @classmethod
    def from_json(cls, value: str) -> GameState:
        """署名付きCookieのJSONからゲーム状態を復元する。"""
        payload = json.loads(value)
        initial = cls.initial()
        health_by_enemy = {
            enemy["enemy_id"]: int(enemy["hit_points"])
            for enemy in payload.get("enemies", [])
        }
        enemies = tuple(
            replace(
                enemy, hit_points=health_by_enemy.get(enemy.enemy_id, enemy.hit_points)
            )
            for enemy in initial.enemies
        )
        return replace(
            initial,
            experience=int(payload.get("experience", 0)),
            enemies=enemies,
            selected_enemy_id=payload.get("selected_enemy_id"),
            selected_line_id=payload.get("selected_line_id"),
            tool_history=tuple(payload.get("tool_history", ())),
        )
