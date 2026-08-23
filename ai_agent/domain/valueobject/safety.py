from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class GuardrailStage(StrEnum):
    """安全性を確認する実行段階。"""

    INPUT = "input"
    TOOL_INPUT = "tool_input"
    TOOL_OUTPUT = "tool_output"
    OUTPUT = "output"


@dataclass(frozen=True)
class GuardrailResult:
    """ガードレールの判定結果を表す値オブジェクト。"""

    stage: GuardrailStage
    allowed: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """SDKのガードレール情報として渡せる辞書へ変換する。"""
        return asdict(self)
