"""確認用の辞書表記揺れCSVを生成する。"""

import json
import logging
import os
from typing import Protocol

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from openai import OpenAIError

from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import LlmModelProfile, ModelDefaults, OpenAIGptConfig

from ..valueobject.reading_support import (
    ReadingSupportCandidateResult,
    ReadingSupportDefinition,
    ReadingSupportImportError,
    normalize_word,
)
from .reading_support_import import ReadingSupportCsvImporter

logger = logging.getLogger(__name__)


class CandidateGenerationError(Exception):
    """候補生成で外部サービスや応答形式を利用できない場合の例外。"""


class VariantGenerator(Protocol):
    """辞書の1行から、意味と読みが同じ別表記だけを返す境界。"""

    def generate(self, row: ReadingSupportDefinition) -> list[str]:
        """元行は含めず、別表記の単語だけを返す。"""


class OpenAIVariantGenerator:
    """共通LLMサービスで辞書の1行ごとに別表記を提案する。"""

    model_name = ModelDefaults.TEXT_MODEL

    def generate(self, row: ReadingSupportDefinition) -> list[str]:
        """元行の読みと説明から、同義・同音の表記だけをJSONで受け取る。"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise CandidateGenerationError("OPENAI_API_KEY が設定されていません。")
        profile = LlmModelProfile(model=self.model_name, reasoning_effort="low")
        messages = [
            Message(
                role=RoleType.SYSTEM,
                content=(
                    "あなたは日本語の辞書編集者です。入力のwordと意味・読みが完全に同じ"
                    "別表記だけを提案してください。同義語、類義語、読みが違う語、"
                    "確証のない表記は提案しないでください。全角・半角、英字の大小文字、"
                    "空白だけが違う語は提案しないでください。URLは生成しないでください。"
                    'JSONのみで {"variants":[{"word":"別表記",'
                    '"same_meaning_and_reading":true}]} を返してください。'
                    "候補がなければvariantsを空配列にしてください。"
                ),
            ),
            Message(
                role=RoleType.USER,
                content=json.dumps(
                    {
                        "word": row.word,
                        "reading": row.reading,
                        "description": row.description,
                    },
                    ensure_ascii=False,
                ),
            ),
        ]
        try:
            response = LlmCompletionService(
                OpenAIGptConfig.from_profile(profile, api_key=api_key, max_tokens=1000)
            ).retrieve_answer(
                messages, max_messages=2, response_format={"type": "json_object"}
            )
            payload = json.loads(response.answer)
        except (OpenAIError, ValueError) as error:
            logger.warning("Dictionary variant generation failed: %s", error)
            raise CandidateGenerationError(
                "GPTの応答を取得できませんでした。"
            ) from error

        if not isinstance(payload, dict) or not isinstance(
            payload.get("variants"), list
        ):
            raise CandidateGenerationError("GPTの候補形式が正しくありませんでした。")
        variants = payload["variants"]
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("word"), str)
            or item.get("same_meaning_and_reading") is not True
            for item in variants
        ):
            raise CandidateGenerationError("GPTの候補形式が正しくありませんでした。")
        return [item["word"] for item in variants]


class ReadingSupportCandidateService:
    """既存形式のCSVを検証し、元行を残して候補行を組み立てる。"""

    def __init__(self, generator: VariantGenerator | None = None) -> None:
        self.generator = generator or OpenAIVariantGenerator()

    def generate_csv(self, source: bytes | str) -> ReadingSupportCandidateResult:
        """入力行を変更せず、正規化済み重複を除いた候補を後ろに加える。"""
        parsed_rows, errors = ReadingSupportCsvImporter.read_rows(
            source, preserve_values=True
        )
        if errors:
            return ReadingSupportCandidateResult(errors=tuple(errors))

        originals: list[tuple[int, ReadingSupportDefinition]] = []
        seen: set[str] = set()
        for line_number, values in parsed_rows:
            row = ReadingSupportDefinition(
                word=values["word"],
                reading=values["reading"],
                description=values["description"],
                source_url=values["source_url"],
                generated_by_model=values.get("generated_by_model", ""),
            )
            error = self._validate_original(row)
            normalized = normalize_word(row.word)
            if normalized in seen:
                error = "同じCSV内に同じ単語が複数あります。"
            if error:
                errors.append(ReadingSupportImportError(line_number, error))
            seen.add(normalized)
            originals.append((line_number, row))
        if errors:
            return ReadingSupportCandidateResult(errors=tuple(errors))

        rows: list[ReadingSupportDefinition] = []
        warnings: list[ReadingSupportImportError] = []
        generation_failed = False
        model_name = getattr(self.generator, "model_name", "")
        if not isinstance(model_name, str):
            model_name = ""
        for line_number, original in originals:
            rows.append(original)
            try:
                words = self.generator.generate(original)
            except CandidateGenerationError as error:
                generation_failed = True
                warnings.append(
                    ReadingSupportImportError(
                        line_number,
                        f"{error} 元の行のみ出力しました。",
                    )
                )
                continue
            candidate_count = 0
            for word in words:
                candidate = word.strip()
                normalized = normalize_word(candidate)
                if (
                    not candidate
                    or len(candidate) > 255
                    or candidate[0] in "=+-@"
                    or any(ord(char) < 32 for char in candidate)
                    or normalized in seen
                ):
                    continue
                seen.add(normalized)
                candidate_count += 1
                rows.append(
                    ReadingSupportDefinition(
                        word=candidate,
                        reading=original.reading,
                        description=original.description,
                        source_url="",
                        generated_by_model=model_name,
                    )
                )
            if candidate_count == 0:
                reason = (
                    "同じ意味・読みの別表記候補は見つかりませんでした。"
                    if not words
                    else "提案は既存行との重複または不正な単語のため除外しました。"
                )
                warnings.append(ReadingSupportImportError(line_number, reason))
        return ReadingSupportCandidateResult(
            rows=tuple(rows),
            warnings=tuple(warnings),
            generation_failed=generation_failed,
        )

    @staticmethod
    def _validate_original(row: ReadingSupportDefinition) -> str:
        """既存CSV取り込みの必須値とURL形式を生成前に確認する。"""
        if not normalize_word(row.word) or len(row.word.strip()) > 255:
            return "単語を入力し、255文字以内にしてください。"
        if not row.reading.strip() or len(row.reading.strip()) > 255:
            return "読みを入力し、255文字以内にしてください。"
        if not row.description.strip():
            return "説明を入力してください。"
        if row.source_url.strip():
            if len(row.source_url.strip()) > 200:
                return "出典URLは200文字以内にしてください。"
            try:
                URLValidator()(row.source_url.strip())
            except ValidationError:
                return "出典URLの形式が正しくありません。"
        if len(row.generated_by_model.strip()) > 100:
            return "生成モデルは100文字以内にしてください。"
        return ""
