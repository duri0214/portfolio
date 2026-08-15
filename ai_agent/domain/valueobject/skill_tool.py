from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SkillCategory(StrEnum):
    """ゲーム内で敵に対応する教科。

    Attributes:
        LANGUAGE: 国語のSkill。
        MATHEMATICS: 算数のSkill。
        SCIENCE: 理科のSkill。
    """

    LANGUAGE = "language"
    MATHEMATICS = "mathematics"
    SCIENCE = "science"


@dataclass(frozen=True)
class SkillToolDefinition:
    """Agentへ公開するSkill Toolのメタデータ。

    Attributes:
        name: 実装上のFunction Tool名。
        display_name: UIに表示する日本語名。
        category: 対応する教科。
        power: 成功時に敵へ与えるダメージ。
        experience: 成功時に加算する経験値。
    """

    name: str
    display_name: str
    category: SkillCategory
    power: int
    experience: int

    @property
    def category_display_name(self) -> str:
        """画面に表示する教科名を返す。"""
        return {
            SkillCategory.LANGUAGE: "国語",
            SkillCategory.MATHEMATICS: "算数",
            SkillCategory.SCIENCE: "理科",
        }[self.category]


@dataclass(frozen=True)
class SkillToolResult:
    """Skill Tool 1回分の構造化された実行結果。

    Attributes:
        tool_name: 実行したFunction Tool名。
        display_name: UI表示用のSkill名。
        success: Skillが成功したかどうか。
        target_enemy_id: 効果対象の敵識別子。
        damage: 今回与えたダメージ。
        experience_gained: 今回獲得した経験値。
        enemy_remaining_hit_points: 実行後の敵の体力。
        message: UIやAgentが利用する結果メッセージ。
    """

    tool_name: str
    display_name: str
    success: bool
    target_enemy_id: str
    damage: int
    experience_gained: int
    enemy_remaining_hit_points: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        """SDKのTool出力として渡せる辞書へ変換する。"""
        return {
            "tool_name": self.tool_name,
            "display_name": self.display_name,
            "success": self.success,
            "target_enemy_id": self.target_enemy_id,
            "damage": self.damage,
            "experience_gained": self.experience_gained,
            "enemy_remaining_hit_points": self.enemy_remaining_hit_points,
            "message": self.message,
        }
