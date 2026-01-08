from enum import Enum
from dataclasses import dataclass


class GuardRailSignal(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


@dataclass(frozen=True)
class SemanticGuardResult:
    signal: GuardRailSignal
    reason: str | None = None
    detail: str | None = None


class SemanticGuardException(Exception):
    def __init__(self, guard_result: SemanticGuardResult):
        self.result = guard_result
        super().__init__(
            f"GuardRail Triggered: {guard_result.reason} - {guard_result.detail}"
        )
