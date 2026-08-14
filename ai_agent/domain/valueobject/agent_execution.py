from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class AgentRunStatus(StrEnum):
    """Agent実行の終了状態。

    Attributes:
        COMPLETED: Agentが最終出力まで到達した状態。
        BLOCKED: 入力・出力・Toolのガードレールで実行を遮断した状態。
        FAILED: SDKや外部プロバイダーなどの予期しない失敗状態。
        TIMED_OUT: 指定された実行時間を超えた状態。
    """

    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class ToolCall:
    """Agentが選択した1回のFunction Tool呼び出しを表す値。

    Attributes:
        call_id: SDKが発行したTool呼び出しの識別子。
        name: 選択されたFunction Tool名。
        arguments: Toolへ渡された構造化引数。
        sequence: 実行結果内での呼び出し順。
    """

    call_id: str
    name: str
    arguments: dict[str, Any]
    sequence: int


@dataclass(frozen=True)
class ToolResult:
    """Function Toolの実行結果を表す値。

    Attributes:
        call_id: 対応するTool呼び出しの識別子。
        name: 実行されたFunction Tool名。
        output: Toolが返した構造化または文字列の出力。
        succeeded: Tool実行が成功したかどうか。
        sequence: 実行結果内での結果順。
        error: 失敗時のエラー内容。成功時はNone。
    """

    call_id: str
    name: str
    output: Any
    succeeded: bool
    sequence: int
    error: str | None = None


@dataclass(frozen=True)
class Report:
    """1回のAgent実行を後続のUIや履歴保存へ渡す最終レポート。

    Attributes:
        output: Agentが生成した最終出力。
        status: 実行の終了状態。
        tool_calls: Agentが選択したTool呼び出しの一覧。
        tool_results: Toolの実行結果一覧。
        turns: SDKが処理したモデル応答ターン数。
        error: 実行失敗や遮断の理由。正常終了時はNone。
    """

    output: Any
    status: AgentRunStatus
    tool_calls: tuple[ToolCall, ...]
    tool_results: tuple[ToolResult, ...]
    turns: int
    error: str | None = None


@dataclass(frozen=True)
class AgentRun:
    """1回の依頼について、入力・Tool履歴・最終レポートを保持する実行スナップショット。

    Attributes:
        run_id: 実行を一意に識別するUUID文字列表現。
        input_text: Agentへ渡した入力。
        max_turns: 実行時に指定した最大ターン数。
        status: 実行の終了状態。
        started_at: 実行開始時刻（UTC）。
        completed_at: 実行終了時刻（UTC）。
        tool_calls: Agentが選択したTool呼び出しの一覧。
        tool_results: Toolの実行結果一覧。
        report: 出力と実行履歴をまとめた最終レポート。
    """

    run_id: str
    input_text: str
    max_turns: int
    status: AgentRunStatus
    started_at: datetime
    completed_at: datetime
    tool_calls: tuple[ToolCall, ...]
    tool_results: tuple[ToolResult, ...]
    report: Report

    def to_dict(self) -> dict[str, Any]:
        """実行履歴をJSONへ変換可能な辞書として返します。"""
        payload = asdict(self)
        return json.loads(
            json.dumps(
                payload,
                default=lambda value: (
                    value.value
                    if isinstance(value, StrEnum)
                    else (
                        value.isoformat() if isinstance(value, datetime) else str(value)
                    )
                ),
            )
        )
