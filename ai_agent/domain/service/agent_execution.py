from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents import Agent, Runner
from agents.exceptions import (
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    ToolInputGuardrailTripwireTriggered,
    ToolOutputGuardrailTripwireTriggered,
)

from ai_agent.domain.valueobject.agent_execution import (
    AgentRun,
    AgentRunStatus,
    Report,
    ToolCall,
    ToolResult,
)


class AgentExecutionService:
    """OpenAI Agents SDKによる単一依頼のAgent実行を管理するサービス。

    Runnerへの委譲、Tool Call/Resultの追跡、上限ターン数とタイムアウトの適用、
    失敗時の構造化された結果作成を担当します。実行履歴はDBへ保存せず、後続の
    履歴保存やUIへ渡せるAgentRunとして返します。
    """

    def __init__(
        self,
        name: str,
        instructions: str,
        tools: Iterable[Any] = (),
        input_guardrails: Iterable[Any] = (),
        output_guardrails: Iterable[Any] = (),
        model: str = "gpt-5-mini",
        runner: Any = Runner,
    ) -> None:
        self.agent = Agent(
            name=name,
            instructions=instructions,
            model=model,
            tools=list(tools),
            input_guardrails=list(input_guardrails),
            output_guardrails=list(output_guardrails),
        )
        self.runner = runner

    async def run(
        self,
        input_text: str,
        *,
        max_turns: int = 10,
        timeout_seconds: float | None = 30.0,
    ) -> AgentRun:
        """1件の入力をAgentへ渡し、Tool Chainの実行結果を返します。

        Args:
            input_text: Agentが解釈するユーザー入力。
            max_turns: AgentがTool実行を継続できる最大ターン数。
            timeout_seconds: 実行全体の制限時間。Noneの場合は制限しません。

        Returns:
            成功・遮断・失敗・タイムアウトのいずれかを含むAgentRun。

        Raises:
            ValueError: 入力が空、または上限値が不正な場合。
        """
        self._validate_input(input_text, max_turns, timeout_seconds)
        started_at = datetime.now(timezone.utc)
        tool_calls: tuple[ToolCall, ...] = ()
        tool_results: tuple[ToolResult, ...] = ()

        try:
            result = self.runner.run(
                self.agent,
                input_text,
                max_turns=max_turns,
            )
            if inspect.isawaitable(result):
                if timeout_seconds is None:
                    result = await result
                else:
                    result = await asyncio.wait_for(result, timeout_seconds)

            tool_calls, tool_results = self._extract_tool_trace(result)
            status = AgentRunStatus.COMPLETED
            error = None
            output = self._serialize_output(result.final_output)
            turns = len(getattr(result, "raw_responses", ()))
        except (
            InputGuardrailTripwireTriggered,
            OutputGuardrailTripwireTriggered,
            ToolInputGuardrailTripwireTriggered,
            ToolOutputGuardrailTripwireTriggered,
        ) as exception:
            status = AgentRunStatus.BLOCKED
            error = self._exception_message(exception)
            output = None
            turns = 0
        except TimeoutError as exception:
            status = AgentRunStatus.TIMED_OUT
            error = self._exception_message(
                exception, "Agent実行がタイムアウトしました"
            )
            output = None
            turns = 0
        except Exception as exception:
            status = AgentRunStatus.FAILED
            error = self._exception_message(exception)
            output = None
            turns = 0

        completed_at = datetime.now(timezone.utc)
        report = Report(
            output=output,
            status=status,
            tool_calls=tool_calls,
            tool_results=tool_results,
            turns=turns,
            error=error,
        )
        return AgentRun(
            run_id=str(uuid4()),
            input_text=input_text,
            max_turns=max_turns,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            tool_calls=tool_calls,
            tool_results=tool_results,
            report=report,
        )

    def run_sync(
        self,
        input_text: str,
        *,
        max_turns: int = 10,
        timeout_seconds: float | None = 30.0,
    ) -> AgentRun:
        """同期呼び出し用の薄いラッパーとしてAgent実行を返します。"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.run(
                    input_text,
                    max_turns=max_turns,
                    timeout_seconds=timeout_seconds,
                )
            )
        raise RuntimeError("イベントループ実行中はrun()をawaitしてください")

    async def stream(
        self,
        input_text: str,
        *,
        max_turns: int = 10,
        timeout_seconds: float | None = 30.0,
    ):
        """Agentの意味イベントをTool単位で逐次返します。"""
        self._validate_input(input_text, max_turns, timeout_seconds)
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        tool_calls: tuple[ToolCall, ...] = ()
        tool_results: tuple[ToolResult, ...] = ()
        yield {"type": "run.started", "run_id": run_id}

        result = None
        try:
            result = self.runner.run_streamed(
                self.agent,
                input_text,
                max_turns=max_turns,
            )
            if inspect.isawaitable(result):
                result = await result
            names_by_call_id: dict[str, str] = {}
            sequence = 0

            async def consume_events():
                nonlocal sequence
                async for stream_event in result.stream_events():
                    event = self._stream_event(stream_event, names_by_call_id, sequence)
                    if event is not None:
                        if event["type"] == "tool.selected":
                            sequence = event["sequence"]
                        yield event

            if timeout_seconds is None:
                async for event in consume_events():
                    yield event
            else:
                async with asyncio.timeout(timeout_seconds):
                    async for event in consume_events():
                        yield event

            tool_calls, tool_results = self._extract_tool_trace(result)
            status = AgentRunStatus.COMPLETED
            error = None
            output = self._serialize_output(result.final_output)
            turns = len(getattr(result, "raw_responses", ()))
        except (
            InputGuardrailTripwireTriggered,
            OutputGuardrailTripwireTriggered,
            ToolInputGuardrailTripwireTriggered,
            ToolOutputGuardrailTripwireTriggered,
        ) as exception:
            if result is not None:
                tool_calls, tool_results = self._extract_tool_trace(result)
            status = AgentRunStatus.BLOCKED
            error = self._exception_message(exception)
            output = None
            turns = 0
        except TimeoutError as exception:
            if result is not None:
                tool_calls, tool_results = self._extract_tool_trace(result)
            status = AgentRunStatus.TIMED_OUT
            error = self._exception_message(
                exception, "Agent実行がタイムアウトしました"
            )
            output = None
            turns = 0
        except Exception as exception:
            if result is not None:
                tool_calls, tool_results = self._extract_tool_trace(result)
            status = AgentRunStatus.FAILED
            error = self._exception_message(exception)
            output = None
            turns = 0

        completed_at = datetime.now(timezone.utc)
        report = Report(
            output=output,
            status=status,
            tool_calls=tool_calls,
            tool_results=tool_results,
            turns=turns,
            error=error,
        )
        run = AgentRun(
            run_id=run_id,
            input_text=input_text,
            max_turns=max_turns,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            tool_calls=tool_calls,
            tool_results=tool_results,
            report=report,
        )
        yield {
            "type": "report.completed",
            "run_id": run_id,
            "status": status.value,
            "output": output,
            "error": error,
            "run": run,
        }

    @classmethod
    def _stream_event(
        cls, stream_event: Any, names_by_call_id: dict[str, str], sequence: int
    ) -> dict[str, Any] | None:
        if getattr(stream_event, "type", "") != "run_item_stream_event":
            return None
        item = getattr(stream_event, "item", None)
        raw_item = getattr(item, "raw_item", None)
        if getattr(stream_event, "name", "") == "tool_called":
            call_id = cls._raw_value(raw_item, "call_id") or cls._raw_value(
                raw_item, "id", ""
            )
            name = cls._raw_value(raw_item, "name", "")
            names_by_call_id[call_id] = name
            arguments = cls._parse_arguments(
                cls._raw_value(raw_item, "arguments", "{}")
            )
            sequence += 1
            return {
                "type": "tool.selected",
                "call_id": call_id,
                "tool_name": name,
                "arguments": arguments,
                "sequence": sequence,
            }
        if getattr(stream_event, "name", "") != "tool_output":
            return None
        call_id = cls._raw_value(raw_item, "call_id") or cls._raw_value(
            raw_item, "id", ""
        )
        tool_error = cls._raw_value(raw_item, "error", None)
        output = getattr(item, "output", None)
        if output is None:
            output = cls._raw_value(raw_item, "output", None)
        return {
            "type": "tool.failed" if tool_error is not None else "tool.completed",
            "call_id": call_id,
            "tool_name": names_by_call_id.get(call_id, ""),
            "sequence": sequence,
            "output": cls._serialize_output(output),
            "error": str(tool_error) if tool_error is not None else None,
        }

    @staticmethod
    def _validate_input(
        input_text: str, max_turns: int, timeout_seconds: float | None
    ) -> None:
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError("input_text must not be empty")
        if max_turns < 1:
            raise ValueError("max_turns must be greater than zero")
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

    @staticmethod
    def _raw_value(raw_item: Any, name: str, default: Any = None) -> Any:
        """SDKの辞書形式とオブジェクト形式のraw itemから値を読む。"""
        if isinstance(raw_item, dict):
            return raw_item.get(name, default)
        return getattr(raw_item, name, default)

    @classmethod
    def _extract_tool_trace(
        cls, result: Any
    ) -> tuple[tuple[ToolCall, ...], tuple[ToolResult, ...]]:
        calls: list[ToolCall] = []
        results: list[ToolResult] = []
        names_by_call_id: dict[str, str] = {}

        for item in getattr(result, "new_items", ()):
            raw_item = getattr(item, "raw_item", None)
            item_type = getattr(item, "type", "")
            if item_type == "tool_call_item":
                call_id = cls._raw_value(raw_item, "call_id") or cls._raw_value(
                    raw_item, "id", ""
                )
                name = cls._raw_value(raw_item, "name", "")
                names_by_call_id[call_id] = name
                calls.append(
                    ToolCall(
                        call_id=call_id,
                        name=name,
                        arguments=cls._parse_arguments(
                            cls._raw_value(raw_item, "arguments", "{}")
                        ),
                        sequence=len(calls) + 1,
                    )
                )
            elif item_type == "tool_call_output_item":
                call_id = cls._raw_value(raw_item, "call_id") or cls._raw_value(
                    raw_item, "id", ""
                )
                tool_error = cls._raw_value(raw_item, "error", None)
                output = getattr(item, "output", None)
                if output is None:
                    output = cls._raw_value(raw_item, "output", None)
                results.append(
                    ToolResult(
                        call_id=call_id,
                        name=names_by_call_id.get(call_id, ""),
                        output=cls._serialize_output(output),
                        succeeded=tool_error is None,
                        sequence=len(results) + 1,
                        error=(str(tool_error) if tool_error is not None else None),
                    )
                )

        return tuple(calls), tuple(results)

    @staticmethod
    def _parse_arguments(arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if not isinstance(arguments, str):
            return {"_raw": arguments}
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return {"_raw": arguments}
        return parsed if isinstance(parsed, dict) else {"_raw": parsed}

    @staticmethod
    def _serialize_output(output: Any) -> Any:
        if hasattr(output, "model_dump"):
            return output.model_dump(mode="json")
        return output

    @staticmethod
    def _exception_message(exception: Exception, fallback: str | None = None) -> str:
        return str(exception) or fallback or exception.__class__.__name__
