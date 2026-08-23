from __future__ import annotations

import json
import re
from typing import Any

from agents.guardrail import GuardrailFunctionOutput, InputGuardrail, OutputGuardrail
from agents.tool_guardrails import (
    ToolGuardrailFunctionOutput,
    ToolInputGuardrail,
    ToolOutputGuardrail,
)

from ai_agent.domain.valueobject.safety import GuardrailResult, GuardrailStage


class SafetyPolicy:
    """Agentに渡す入力、Toolの入出力、最終出力の安全性を判定する。"""

    _DANGEROUS_PATTERNS = (
        re.compile(
            r"ignore\s+(?:all\s+)?(?:previous|prior|earlier)\s+instructions", re.I
        ),
        re.compile(r"(?:system|developer)\s+prompt", re.I),
        re.compile(
            r"(?:rm\s+-rf|rm\s+--no-preserve-root|del\s+/[fq].*|format\s+[a-z]:)", re.I
        ),
        re.compile(
            r"(?:powershell(?:\.exe)?|cmd(?:\.exe)?\s+/c|bash\s+-c|sh\s+-c|python\s+-c)",
            re.I,
        ),
        re.compile(r"(?:curl|wget).*\|\s*(?:sh|bash)", re.I | re.S),
        re.compile(r"(?:シェル(?:コマンド|実行)|コマンドを実行)", re.I),
    )

    def __init__(
        self,
        *,
        max_input_length: int = 500,
        max_tool_payload_length: int = 4000,
        max_output_length: int = 4000,
    ) -> None:
        if max_input_length < 1:
            raise ValueError("max_input_length must be greater than zero")
        if max_tool_payload_length < 1:
            raise ValueError("max_tool_payload_length must be greater than zero")
        if max_output_length < 1:
            raise ValueError("max_output_length must be greater than zero")
        self.max_input_length = max_input_length
        self.max_tool_payload_length = max_tool_payload_length
        self.max_output_length = max_output_length

    def check_input(self, input_text: str) -> GuardrailResult:
        """Agent入力の長さと危険な命令の有無を確認する。"""
        if not isinstance(input_text, str):
            return self._deny(GuardrailStage.INPUT, "入力は文字列で指定してください")
        if len(input_text) > self.max_input_length:
            return self._deny(
                GuardrailStage.INPUT,
                f"入力が長すぎます（最大{self.max_input_length}文字）",
            )
        return self._check_text(GuardrailStage.INPUT, input_text)

    def check_tool_arguments(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> GuardrailResult:
        """Tool名と構造化引数を確認する。"""
        if not isinstance(tool_name, str) or not tool_name.strip():
            return self._deny(GuardrailStage.TOOL_INPUT, "Tool名が不正です")
        if not isinstance(arguments, dict):
            return self._deny(
                GuardrailStage.TOOL_INPUT,
                f"{tool_name}の引数はJSONオブジェクトで指定してください",
            )
        return self._check_payload(
            GuardrailStage.TOOL_INPUT,
            arguments,
            self.max_tool_payload_length,
            f"{tool_name}の引数",
        )

    def check_tool_result(self, tool_name: str, output: Any) -> GuardrailResult:
        """Tool結果が安全にJSON化でき、上限内であることを確認する。"""
        if not isinstance(tool_name, str) or not tool_name.strip():
            return self._deny(GuardrailStage.TOOL_OUTPUT, "Tool名が不正です")
        return self._check_payload(
            GuardrailStage.TOOL_OUTPUT,
            output,
            self.max_tool_payload_length,
            f"{tool_name}の結果",
        )

    def check_output(self, output: Any) -> GuardrailResult:
        """Agentの最終出力を確認する。"""
        return self._check_payload(
            GuardrailStage.OUTPUT,
            output,
            self.max_output_length,
            "Agentの最終出力",
        )

    def input_guardrail(self) -> InputGuardrail[Any]:
        """OpenAI Agents SDKへ渡す入力ガードレールを生成する。"""
        return InputGuardrail(
            self._sdk_input_guardrail,
            name="safety_input",
            run_in_parallel=False,
        )

    def output_guardrail(self) -> OutputGuardrail[Any]:
        """OpenAI Agents SDKへ渡す最終出力ガードレールを生成する。"""
        return OutputGuardrail(self._sdk_output_guardrail, name="safety_output")

    def tool_input_guardrail(self) -> ToolInputGuardrail[Any]:
        """OpenAI Agents SDKへ渡すTool入力ガードレールを生成する。"""
        return ToolInputGuardrail(
            self._sdk_tool_input_guardrail,
            name="safety_tool_input",
        )

    def tool_output_guardrail(self) -> ToolOutputGuardrail[Any]:
        """OpenAI Agents SDKへ渡すTool出力ガードレールを生成する。"""
        return ToolOutputGuardrail(
            self._sdk_tool_output_guardrail,
            name="safety_tool_output",
        )

    def _sdk_input_guardrail(
        self, _context: Any, _agent: Any, input_value: Any
    ) -> GuardrailFunctionOutput:
        value = input_value if isinstance(input_value, str) else str(input_value)
        result = self.check_input(value)
        return GuardrailFunctionOutput(
            output_info=result.to_dict(),
            tripwire_triggered=not result.allowed,
        )

    def _sdk_output_guardrail(
        self, _context: Any, _agent: Any, output: Any
    ) -> GuardrailFunctionOutput:
        result = self.check_output(output)
        return GuardrailFunctionOutput(
            output_info=result.to_dict(),
            tripwire_triggered=not result.allowed,
        )

    def _sdk_tool_input_guardrail(self, data: Any) -> ToolGuardrailFunctionOutput:
        tool_name = str(data.context.tool_name)
        try:
            arguments = json.loads(data.context.tool_arguments)
        except (TypeError, json.JSONDecodeError):
            result = self._deny(
                GuardrailStage.TOOL_INPUT,
                f"{tool_name}の引数は有効なJSONではありません",
            )
        else:
            result = self.check_tool_arguments(tool_name, arguments)
        return self._tool_guardrail_output(result)

    def _sdk_tool_output_guardrail(self, data: Any) -> ToolGuardrailFunctionOutput:
        result = self.check_tool_result(str(data.context.tool_name), data.output)
        return self._tool_guardrail_output(result)

    @classmethod
    def _tool_guardrail_output(
        cls, result: GuardrailResult
    ) -> ToolGuardrailFunctionOutput:
        if result.allowed:
            return ToolGuardrailFunctionOutput.allow(output_info=result.to_dict())
        return ToolGuardrailFunctionOutput.raise_exception(output_info=result.to_dict())

    @classmethod
    def _check_text(cls, stage: GuardrailStage, value: str) -> GuardrailResult:
        if any(pattern.search(value) for pattern in cls._DANGEROUS_PATTERNS):
            return cls._deny(stage, "危険な命令やプロンプト操作を含む入力は扱えません")
        return GuardrailResult(stage=stage, allowed=True)

    @classmethod
    def _check_payload(
        cls,
        stage: GuardrailStage,
        value: Any,
        max_length: int,
        label: str,
    ) -> GuardrailResult:
        try:
            serialized = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError):
            return cls._deny(stage, f"{label}を安全なJSONとして扱えません")
        if len(serialized) > max_length:
            return cls._deny(
                stage,
                f"{label}が大きすぎます（最大{max_length}文字）",
            )
        return cls._check_text(stage, serialized)

    @staticmethod
    def _deny(stage: GuardrailStage, reason: str) -> GuardrailResult:
        return GuardrailResult(stage=stage, allowed=False, reason=reason)
