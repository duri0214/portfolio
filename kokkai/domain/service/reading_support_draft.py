from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.db import transaction
from openai import OpenAIError

from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import ModelDefaults, OpenAIGptConfig

from ...models import (
    ReadingSupportDraft,
    ReadingSupportDraftCandidate,
    ReadingSupportEntry,
)
from ..valueobject.reading_support import normalize_surface

logger = logging.getLogger(__name__)


class ReadingSupportDraftGenerationError(Exception):
    """辞書候補の取得または生成に失敗した場合の例外。"""


class SourceTextFetcher(Protocol):
    """Webページから候補生成用の本文を取得する境界。"""

    def fetch(self, url: str) -> str:
        """URLから本文を抽出する。"""


class CandidateGenerator(Protocol):
    """辞書候補を生成するLLM境界。"""

    model: str

    def generate(self, source_text: str, source_url: str = "") -> list[dict[str, Any]]:
        """本文から辞書候補を作成する。"""


class WebSourceTextFetcher:
    """Webページを取得し、HTMLから本文テキストだけを取り出す。"""

    USER_AGENT = "portfolio-kokkai-reading-support/1.0"

    def fetch(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ReadingSupportDraftGenerationError(
                "http または https のURLを指定してください。"
            )
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("Failed to fetch dictionary source %s: %s", url, error)
            raise ReadingSupportDraftGenerationError(
                "指定したWebページを取得できませんでした。"
            ) from error

        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = soup.get_text("\n", strip=True)
        if not text:
            raise ReadingSupportDraftGenerationError(
                "Webページから候補生成に使える本文を取得できませんでした。"
            )
        return text


class OpenAIReadingSupportCandidateGenerator:
    """Web情報から用語・読み補正候補をJSONで生成するOpenAIアダプター。"""

    model = ModelDefaults.TAXONOMY_CANDIDATE.model

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")

    def generate(self, source_text: str, source_url: str = "") -> list[dict[str, Any]]:
        if not self.api_key:
            raise ReadingSupportDraftGenerationError(
                "OPENAI_API_KEY is not configured."
            )

        messages = [
            Message(
                role=RoleType.SYSTEM,
                content=(
                    "あなたは国会会議録の学習支援辞書を作る編集者です。"
                    "入力された一次資料だけを根拠に、会議録で意味や読みを補助すると有用な"
                    "用語候補または読み補正候補を作成してください。"
                    "不確かな候補は needs_review=true にしてください。"
                    "読み補正だけの候補は entry_type=reading_override とし、"
                    "description・category・source_url は空でも構いません。"
                    "用語候補は source_url を入力URLにし、根拠が不明なら要確認にしてください。"
                    "JSON以外を返さないでください。"
                ),
            ),
            Message(
                role=RoleType.USER,
                content=json.dumps(
                    {
                        "source_url": source_url,
                        "source_text": source_text,
                        "output_schema": {
                            "candidates": [
                                {
                                    "entry_type": "term or reading_override",
                                    "surface": "string",
                                    "reading": "string",
                                    "description": "string",
                                    "category": "string",
                                    "source_url": "string",
                                    "needs_review": "boolean",
                                    "review_note": "string",
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
            ),
        ]
        try:
            response = LlmCompletionService(
                OpenAIGptConfig.from_profile(
                    ModelDefaults.TAXONOMY_CANDIDATE,
                    api_key=self.api_key,
                    max_tokens=4000,
                )
            ).retrieve_answer(
                messages,
                max_messages=len(messages),
                response_format={"type": "json_object"},
            )
        except OpenAIError as error:
            logger.warning("Reading support candidate generation failed: %s", error)
            raise ReadingSupportDraftGenerationError(
                "GPTによる候補生成に失敗しました。"
            ) from error

        try:
            payload = json.loads(response.answer)
        except json.JSONDecodeError as error:
            raise ReadingSupportDraftGenerationError(
                "GPTの候補をJSONとして解釈できませんでした。"
            ) from error
        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(candidates, list):
            raise ReadingSupportDraftGenerationError(
                "GPTの候補形式が正しくありません。"
            )
        return [candidate for candidate in candidates if isinstance(candidate, dict)]


@dataclass(frozen=True)
class CandidateRegistrationResult:
    """承認済み候補の辞書登録結果。"""

    registered: int = 0
    errors: tuple[str, ...] = ()


class ReadingSupportDraftService:
    """Web情報の候補生成と、確認済み候補の辞書登録を管理する。"""

    MAX_SOURCE_CHARACTERS = 50_000

    def __init__(
        self,
        fetcher: SourceTextFetcher | None = None,
        generator: CandidateGenerator | None = None,
    ) -> None:
        self.fetcher = fetcher or WebSourceTextFetcher()
        self.generator = generator or OpenAIReadingSupportCandidateGenerator()

    def create_draft(
        self,
        *,
        source_url: str = "",
        source_text: str = "",
        created_by=None,
    ) -> ReadingSupportDraft:
        """URLまたは貼り付け本文から、確認待ちの下書きを作成する。"""
        source_url = source_url.strip()
        source_text = source_text.strip()
        if source_url:
            fetched_text = self.fetcher.fetch(source_url)
            source_text = "\n\n".join(filter(None, (source_text, fetched_text)))
        if not source_text:
            raise ReadingSupportDraftGenerationError(
                "WebページのURLまたは本文を指定してください。"
            )
        source_text = source_text[: self.MAX_SOURCE_CHARACTERS]
        raw_candidates = self.generator.generate(source_text, source_url)

        with transaction.atomic():
            draft = ReadingSupportDraft.objects.create(
                source_url=source_url,
                source_text=source_text,
                model_name=self.generator.model,
                created_by=created_by,
            )
            for raw_candidate in raw_candidates:
                self._create_candidate(draft, raw_candidate, source_url)
        return draft

    def register_approved_candidates(
        self, draft: ReadingSupportDraft
    ) -> CandidateRegistrationResult:
        """管理者が承認した候補だけを辞書へ登録する。"""
        candidates = list(
            draft.candidates.filter(is_approved=True, is_registered=False).order_by(
                "pk"
            )
        )
        if not candidates:
            return CandidateRegistrationResult(
                errors=("登録承認済みの候補がありません。",)
            )

        prepared: list[tuple[ReadingSupportDraftCandidate, ReadingSupportEntry]] = []
        errors: list[str] = []
        seen_surfaces: set[str] = set()
        for candidate in candidates:
            normalized_surface = normalize_surface(candidate.surface)
            if normalized_surface in seen_surfaces:
                errors.append(f"候補 #{candidate.pk}: 同じ表記が複数あります。")
                continue
            seen_surfaces.add(normalized_surface)
            entry = ReadingSupportEntry.objects.filter(
                normalized_surface=normalized_surface
            ).first()
            if entry is None:
                entry = ReadingSupportEntry()
            entry.entry_type = candidate.entry_type
            entry.surface = candidate.surface
            entry.normalized_surface = normalized_surface
            entry.reading = candidate.reading
            entry.description = candidate.description
            entry.category = candidate.category
            entry.source_url = candidate.source_url
            entry.is_active = True
            try:
                entry.full_clean()
            except ValidationError as error:
                errors.append(
                    f"候補 #{candidate.pk}: {self._validation_message(error)}"
                )
                continue
            prepared.append((candidate, entry))

        if errors:
            return CandidateRegistrationResult(errors=tuple(errors))

        with transaction.atomic():
            for candidate, entry in prepared:
                entry.save()
                candidate.is_registered = True
                candidate.needs_review = False
                candidate.registered_entry = entry
                candidate.save(
                    update_fields=[
                        "is_registered",
                        "needs_review",
                        "registered_entry",
                        "updated_at",
                    ]
                )
            draft.status = ReadingSupportDraft.Status.IMPORTED
            draft.error_message = ""
            draft.save(update_fields=["status", "error_message", "updated_at"])
        return CandidateRegistrationResult(registered=len(prepared))

    @classmethod
    def _create_candidate(
        cls,
        draft: ReadingSupportDraft,
        raw_candidate: dict[str, Any],
        source_url: str,
    ) -> ReadingSupportDraftCandidate:
        entry_type = cls._entry_type(raw_candidate.get("entry_type"))
        surface = cls._string_value(raw_candidate.get("surface"))
        reading = cls._string_value(raw_candidate.get("reading"))
        description = cls._string_value(raw_candidate.get("description"))
        category = cls._string_value(raw_candidate.get("category"))
        candidate_source_url = cls._string_value(raw_candidate.get("source_url"))
        if not candidate_source_url:
            candidate_source_url = source_url
        if candidate_source_url:
            parsed_source_url = urlparse(candidate_source_url)
            if (
                parsed_source_url.scheme not in {"http", "https"}
                or not parsed_source_url.netloc
            ):
                candidate_source_url = ""
        needs_review = bool(raw_candidate.get("needs_review"))
        needs_review = needs_review or not surface or not reading
        if entry_type == ReadingSupportEntry.EntryType.TERM:
            needs_review = needs_review or not all(
                (description, category, candidate_source_url)
            )
        return ReadingSupportDraftCandidate.objects.create(
            draft=draft,
            entry_type=entry_type,
            surface=surface,
            reading=reading,
            description=description,
            category=category,
            source_url=candidate_source_url,
            needs_review=needs_review,
            review_note=cls._string_value(raw_candidate.get("review_note")),
        )

    @staticmethod
    def _entry_type(value: Any) -> str:
        normalized = str(value or "term").strip().casefold()
        if normalized in {
            "reading_override",
            "reading-override",
            "override",
            "読み補正",
        }:
            return ReadingSupportEntry.EntryType.READING_OVERRIDE
        return ReadingSupportEntry.EntryType.TERM

    @staticmethod
    def _string_value(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _validation_message(error: ValidationError) -> str:
        if hasattr(error, "message_dict"):
            return " ".join(
                message
                for field_messages in error.message_dict.values()
                for message in field_messages
            )
        return "; ".join(error.messages)
