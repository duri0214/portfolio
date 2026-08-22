from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class AgentRunStatus(StrEnum):
    """Agent実行の終了状態。

    Attributes:
        COMPLETED: Agentが最終出力まで到達した状態。
        BLOCKED: 入力・出力・Toolのガードレールで実行を遮断した状態。
        FAILED: SDKや外部プロバイダーなどの予期しない失敗状態。
        TIMED_OUT: 指定された実行時間を超えた状態。
        MAX_TURNS_EXCEEDED: Agentが指定された最大ターン数へ到達した状態。
    """

    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    MAX_TURNS_EXCEEDED = "max_turns_exceeded"


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

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ToolCall:
        """保存済みの辞書からTool Callを復元する。"""
        arguments = value.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        return cls(
            call_id=str(value.get("call_id", "")),
            name=str(value.get("name", "")),
            arguments=arguments,
            sequence=int(value.get("sequence", 0)),
        )


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

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ToolResult:
        """保存済みの辞書からTool Resultを復元する。"""
        return cls(
            call_id=str(value.get("call_id", "")),
            name=str(value.get("name", "")),
            output=value.get("output"),
            succeeded=bool(value.get("succeeded", False)),
            sequence=int(value.get("sequence", 0)),
            error=(str(value["error"]) if value.get("error") else None),
        )


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

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Report:
        """保存済みの辞書から最終レポートを復元する。"""
        status = _status_from_value(value.get("status"))
        raw_calls = value.get("tool_calls", ())
        raw_results = value.get("tool_results", ())
        return cls(
            output=value.get("output"),
            status=status,
            tool_calls=tuple(
                ToolCall.from_dict(item) for item in raw_calls if isinstance(item, dict)
            ),
            tool_results=tuple(
                ToolResult.from_dict(item)
                for item in raw_results
                if isinstance(item, dict)
            ),
            turns=int(value.get("turns", 0)),
            error=(str(value["error"]) if value.get("error") else None),
        )


@dataclass(frozen=True)
class ToolChainEvaluation:
    """プリセットセリフの代表Tool Chainと実行結果を比較した値。"""

    line_id: str
    mondai_id: str
    expected: tuple[str, ...]
    actual: tuple[str, ...]
    matched: bool


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

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AgentRun:
        """Djangoセッションに保存した辞書からAgentRunを復元する。"""
        if not isinstance(value, dict):
            raise TypeError("agent run must be a dictionary")
        status = _status_from_value(value.get("status"))
        raw_calls = value.get("tool_calls", ())
        raw_results = value.get("tool_results", ())
        tool_calls = tuple(
            ToolCall.from_dict(item) for item in raw_calls if isinstance(item, dict)
        )
        tool_results = tuple(
            ToolResult.from_dict(item) for item in raw_results if isinstance(item, dict)
        )
        report_payload = value.get("report")
        report = (
            Report.from_dict(report_payload)
            if isinstance(report_payload, dict)
            else Report(
                output=value.get("output"),
                status=status,
                tool_calls=tool_calls,
                tool_results=tool_results,
                turns=int(value.get("turns", 0)),
                error=(str(value["error"]) if value.get("error") else None),
            )
        )
        return cls(
            run_id=str(value.get("run_id", "")),
            input_text=str(value.get("input_text", "")),
            max_turns=int(value.get("max_turns", 0)),
            status=status,
            started_at=_datetime_from_value(value.get("started_at")),
            completed_at=_datetime_from_value(value.get("completed_at")),
            tool_calls=tool_calls,
            tool_results=tool_results,
            report=report,
        )

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


def _status_from_value(value: Any) -> AgentRunStatus:
    try:
        return AgentRunStatus(value)
    except (TypeError, ValueError):
        raise ValueError(f"unknown agent run status: {value}") from None


def _datetime_from_value(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        raise ValueError("agent run timestamp must be an ISO datetime")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
