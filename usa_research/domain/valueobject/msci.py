from dataclasses import dataclass


@dataclass(frozen=True)
class MsciUpdateResult:
    success: bool
    message: str
