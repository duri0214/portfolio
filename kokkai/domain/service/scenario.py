from __future__ import annotations

import hashlib
import json
import logging
import os
from collections import OrderedDict
from dataclasses import dataclass, replace
from typing import Any, Protocol

from openai import OpenAI, OpenAIError

from ...models import Meeting, MeetingScenario, Speech
from ..repository.scenario_repository import ScenarioRepository
from ..valueobject.scenario import (
    ScenarioActorData,
    ScenarioChoiceData,
    ScenarioPayload,
)

logger = logging.getLogger(__name__)


class ScenarioGenerationError(Exception):
    """シナリオ生成用データまたは生成結果が利用できない場合の例外。"""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ScenarioGenerator(Protocol):
    """構造化された会議録からシナリオJSONを生成する境界。"""

    model: str

    def generate(
        self,
        meeting: Meeting,
        actors: list[ScenarioActorData],
        source_chunks: list[str],
    ) -> dict[str, Any]:
        """会議全体の要約と、プレイに必要な判定メタデータを返す。"""

    def generate_choices(
        self,
        meeting: Meeting,
        actor: ScenarioActorData,
        speech: Speech,
        overview: str,
    ) -> dict[str, Any]:
        """選択アクターの発言に対する二択を返す。"""


@dataclass(frozen=True)
class ScenarioAvailability:
    """会議詳細に表示するシナリオの利用可否。"""

    scenario: MeetingScenario | None
    needs_regeneration: bool


class OpenAIScenarioGenerator:
    """会議全体の要約と、発言ごとの二択を生成するOpenAIアダプター。"""

    model = "gpt-4o-mini"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")

    def generate(
        self,
        meeting: Meeting,
        actors: list[ScenarioActorData],
        source_chunks: list[str],
    ) -> dict[str, Any]:
        """会議録全体から、概要・判定メタデータだけを一度生成する。"""
        if not self.api_key:
            raise ScenarioGenerationError("OPENAI_API_KEY is not configured.")

        client = OpenAI(api_key=self.api_key)
        content = self._request_json_content(
            client,
            [
                {
                    "role": "system",
                    "content": (
                        "あなたは国会会議録を題材にした教育用シミュレーションゲームの"
                        "シナリオ編集者です。実在人物が実際に発言したかのようには書かず、"
                        "与えられた一次資料に基づくシミュレーションであることを守ってください。"
                        "会議録全体を読み、overview と判定メタデータだけを作成してください。"
                        "発言ごとのターンや選択肢はここでは作成せず、会議録にない事実も追加しないでください。"
                        "Return valid json only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "会議録全体の要約とゲームの判定メタデータを作る",
                            "meeting": {
                                "min_id": meeting.min_id,
                                "date": meeting.meeting_date.isoformat(),
                                "house": meeting.house,
                                "committee": meeting.committee,
                                "meeting_number": meeting.meeting_number,
                                "source_url": meeting.url,
                            },
                            "actors": [actor.to_prompt_value() for actor in actors],
                            "source_chunks": source_chunks,
                            "output_schema": {
                                "title": "string",
                                "overview": "string",
                                "success_label": "string",
                                "failure_label": "string",
                                "judgment_criteria": "string",
                                "passing_score": "0-100 integer",
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        return self._parse_json_content(content)

    def generate_choices(
        self,
        meeting: Meeting,
        actor: ScenarioActorData,
        speech: Speech,
        overview: str,
    ) -> dict[str, Any]:
        """選択アクターの発言に到達したときだけ、その場面の二択を生成する。"""
        if not self.api_key:
            raise ScenarioGenerationError("OPENAI_API_KEY is not configured.")

        client = OpenAI(api_key=self.api_key)
        content = self._request_json_content(
            client,
            [
                {
                    "role": "system",
                    "content": (
                        "あなたは国会会議録を題材にした教育用ロールプレイの出題者です。"
                        "会議録を基にしたシミュレーションであることを守り、与えられた発言に"
                        "対するプレイヤーの返答候補を二つだけ作ってください。"
                        "適切な返答を一つだけ is_correct=true にし、根拠は発言内容に限定してください。"
                        "Return valid json only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "この発言に対するプレイヤーの返答を二択にする",
                            "meeting": {
                                "min_id": meeting.min_id,
                                "date": meeting.meeting_date.isoformat(),
                                "house": meeting.house,
                                "committee": meeting.committee,
                                "meeting_number": meeting.meeting_number,
                                "source_url": meeting.url,
                            },
                            "overview": overview,
                            "actor": actor.to_prompt_value(),
                            "speech": {
                                "speech_order": speech.speech_order,
                                "speaker_name": speech.speaker_name,
                                "speaker_role": speech.speaker_role or "",
                                "speaker_affiliation": speech.speaker_affiliation or "",
                                "speech_text": speech.speech_text,
                                "source_url": speech.source_url or meeting.url,
                            },
                            "output_schema": {
                                "choices": [
                                    {
                                        "text": "choice text",
                                        "is_correct": "boolean",
                                        "rationale": "source-grounded rationale",
                                    },
                                    {
                                        "text": "choice text",
                                        "is_correct": "boolean",
                                        "rationale": "source-grounded rationale",
                                    },
                                ]
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        return self._parse_json_content(content)

    @staticmethod
    def _parse_json_content(content: str) -> dict[str, Any]:
        try:
            generated = json.loads(content)
        except json.JSONDecodeError as error:
            raise ScenarioGenerationError(
                "The scenario generator returned invalid JSON."
            ) from error
        if not isinstance(generated, dict):
            raise ScenarioGenerationError(
                "The scenario generator returned an invalid payload."
            )
        return generated

    def _request_json_content(
        self, client: OpenAI, messages: list[dict[str, str]]
    ) -> str:
        """OpenAIへJSON出力を要求し、利用者に返せるドメイン例外へ変換する。"""
        try:
            response = client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=messages,
            )
        except OpenAIError as error:
            logger.warning(
                "Scenario generator request failed for model %s: %s",
                self.model,
                error,
            )
            error_text = str(error).lower()
            if any(
                marker in error_text
                for marker in (
                    "tokens per min",
                    "tokens-per-minute",
                    "token per minute",
                )
            ):
                raise ScenarioGenerationError(
                    "The scenario generator exceeded the model's tokens-per-minute "
                    "rate limit. Use a model with a higher rate limit or try again later.",
                    status_code=429,
                ) from error
            if any(
                marker in error_text
                for marker in ("context length", "maximum context", "context window")
            ):
                raise ScenarioGenerationError(
                    "The scenario generator exceeded the model context window. "
                    "Use a shorter meeting.",
                    status_code=413,
                ) from error
            if getattr(error, "status_code", None) == 429:
                raise ScenarioGenerationError(
                    "The scenario generator is rate-limited. Please try again later.",
                    status_code=429,
                ) from error
            raise ScenarioGenerationError(
                "The scenario generator request failed. Check the server log for details."
            ) from error
        content = response.choices[0].message.content
        if not content:
            raise ScenarioGenerationError(
                "The scenario generator returned an empty response."
            )
        return content


class ScenarioService:
    """シナリオカセットの生成・再利用と、会議録由来データの正規化を担う。"""

    PROMPT_VERSION = "meeting-simulation-v2"
    SOURCE_CHUNK_CHARACTERS = 12_000

    def __init__(
        self,
        repository: ScenarioRepository | None = None,
        generator: ScenarioGenerator | None = None,
    ) -> None:
        self.repository = repository or ScenarioRepository()
        self.generator = generator or OpenAIScenarioGenerator()

    def get_availability(self, meeting: Meeting) -> ScenarioAvailability:
        """保存済みシナリオと、会議録更新に伴う再生成要否を返す。"""
        latest_scenario = self.repository.get_latest_scenario(meeting)
        if latest_scenario is None:
            return ScenarioAvailability(scenario=None, needs_regeneration=False)
        source_hash = self._source_hash(self.repository.get_meeting_speeches(meeting))
        return ScenarioAvailability(
            scenario=latest_scenario,
            needs_regeneration=(
                latest_scenario.source_hash != source_hash
                or latest_scenario.prompt_version != self.PROMPT_VERSION
            ),
        )

    def get_or_create(self, meeting: Meeting) -> tuple[MeetingScenario, bool]:
        """同じ条件のシナリオを再利用し、なければ明示操作時にだけ生成する。"""
        speeches = self.repository.get_meeting_speeches(meeting)
        source_hash = self._source_hash(speeches)
        reusable = self.repository.get_reusable_scenario(
            meeting, source_hash, self.PROMPT_VERSION
        )
        if reusable is not None:
            return reusable, False
        return self._generate(meeting, speeches, source_hash), True

    def regenerate(self, meeting: Meeting) -> MeetingScenario:
        """既存のシナリオを上書きせず、新しいバージョンとして生成する。"""
        speeches = self.repository.get_meeting_speeches(meeting)
        return self._generate(meeting, speeches, self._source_hash(speeches))

    def _generate(
        self, meeting: Meeting, speeches: list[Speech], source_hash: str
    ) -> MeetingScenario:
        if not speeches:
            raise ScenarioGenerationError(
                "The meeting does not have imported speeches."
            )
        actors = self._build_actors(speeches)
        source_chunks = self._build_source_chunks(speeches, actors)
        generated = self.generator.generate(meeting, actors, source_chunks)
        payload = self._normalize_payload(generated)
        return self.repository.create_scenario(
            meeting=meeting,
            source_hash=source_hash,
            prompt_version=self.PROMPT_VERSION,
            generator_model=self.generator.model,
            payload=payload,
            actors=actors,
            speeches=speeches,
        )

    @staticmethod
    def _source_hash(speeches: list[Speech]) -> str:
        source = [
            {
                "speech_order": speech.speech_order,
                "speaker_name": speech.speaker_name,
                "speaker_role": speech.speaker_role or "",
                "speaker_affiliation": speech.speaker_affiliation or "",
                "speech_text": speech.speech_text,
                "source_url": speech.source_url,
            }
            for speech in speeches
        ]
        encoded = json.dumps(source, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _build_actors(speeches: list[Speech]) -> list[ScenarioActorData]:
        grouped: OrderedDict[tuple[str, str, str], int] = OrderedDict()
        for speech in speeches:
            identity = (
                speech.speaker_name,
                speech.speaker_role or "",
                speech.speaker_affiliation or "",
            )
            grouped[identity] = grouped.get(identity, 0) + 1
        return [
            ScenarioActorData(
                key=f"actor-{index}",
                display_order=index,
                name=name,
                role=role,
                affiliation=affiliation,
                speech_count=speech_count,
            )
            for index, ((name, role, affiliation), speech_count) in enumerate(
                grouped.items(), start=1
            )
        ]

    def _build_source_chunks(
        self, speeches: list[Speech], actors: list[ScenarioActorData]
    ) -> list[str]:
        actor_keys = {actor.identity: actor.key for actor in actors}
        chunks: list[str] = []
        chunk_parts: list[str] = []
        chunk_length = 0
        for speech in speeches:
            actor_key = actor_keys[
                (
                    speech.speaker_name,
                    speech.speaker_role or "",
                    speech.speaker_affiliation or "",
                )
            ]
            text = (
                f"[speech_order: {speech.speech_order}]\n"
                f"[actor_key: {actor_key}]\n"
                f"[source_url: {speech.source_url or speech.meeting.url}]\n"
                f"{speech.speech_text.strip()}"
            )
            text_parts = [
                text[index : index + self.SOURCE_CHUNK_CHARACTERS]
                for index in range(0, len(text), self.SOURCE_CHUNK_CHARACTERS)
            ] or [text]
            for text_part in text_parts:
                if (
                    chunk_parts
                    and chunk_length + len(text_part) > self.SOURCE_CHUNK_CHARACTERS
                ):
                    chunks.append("\n\n".join(chunk_parts))
                    chunk_parts = []
                    chunk_length = 0
                chunk_parts.append(text_part)
                chunk_length += len(text_part)
        if chunk_parts:
            chunks.append("\n\n".join(chunk_parts))
        return chunks

    @staticmethod
    def _normalize_payload(generated: dict[str, Any]) -> ScenarioPayload:
        """全体要約の生成結果を保存用の値へ正規化する。"""
        return ScenarioPayload(
            title=str(generated.get("title") or "会議録シミュレーション").strip(),
            overview=str(
                generated.get("overview") or "会議録全体を見渡した要約です。"
            ).strip(),
            success_label=str(generated.get("success_label") or "成立").strip(),
            failure_label=str(generated.get("failure_label") or "不成立").strip(),
            judgment_criteria=str(
                generated.get("judgment_criteria") or "根拠発言に沿った選択を行うこと。"
            ).strip(),
            passing_score=ScenarioService._normalize_passing_score(
                generated.get("passing_score")
            ),
        )

    @staticmethod
    def normalize_choices(
        generated: dict[str, Any], actor_key: str, speech_order: int
    ) -> tuple[ScenarioChoiceData, ...]:
        """選択肢を二択・正解一つ・表示順付きの値へ正規化する。"""
        raw_choices = generated.get("choices")
        if not isinstance(raw_choices, list) or len(raw_choices) != 2:
            raise ScenarioGenerationError(
                "The choice generator did not return exactly two choices."
            )

        choices: list[ScenarioChoiceData] = []
        for choice_number, choice in enumerate(raw_choices, start=1):
            if not isinstance(choice, dict) or not str(choice.get("text", "")).strip():
                raise ScenarioGenerationError(
                    "The choice generator returned an invalid choice."
                )
            choices.append(
                ScenarioChoiceData(
                    choice_number=choice_number,
                    text=str(choice["text"]).strip(),
                    is_correct=bool(choice.get("is_correct")),
                    rationale=str(choice.get("rationale", "")).strip(),
                )
            )

        correct_choice_index = next(
            (index for index, choice in enumerate(choices) if choice.is_correct),
            0,
        )
        choices = [
            replace(choice, is_correct=index == correct_choice_index)
            for index, choice in enumerate(choices)
        ]
        order_key = f"{actor_key}:{speech_order}"
        if hashlib.sha256(order_key.encode()).digest()[0] % 2:
            choices.reverse()
        return tuple(
            replace(choice, choice_number=choice_number)
            for choice_number, choice in enumerate(choices, start=1)
        )

    @staticmethod
    def _normalize_passing_score(value: Any) -> int:
        """LLMのスコア値を0から100までの整数へ正規化する。"""
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError):
            return 50
