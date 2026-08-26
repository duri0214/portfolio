from __future__ import annotations

import hashlib
import json
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
    ScenarioTurnData,
)


class ScenarioGenerationError(Exception):
    """シナリオ生成用データまたは生成結果が利用できない場合の例外。"""


class ScenarioGenerator(Protocol):
    """構造化された会議録からシナリオJSONを生成する境界。"""

    model: str

    def generate(
        self,
        meeting: Meeting,
        actors: list[ScenarioActorData],
        source_chunks: list[str],
    ) -> dict[str, Any]:
        """シナリオの構造化データを返す。"""


@dataclass(frozen=True)
class ScenarioAvailability:
    """会議詳細に表示するシナリオの利用可否。"""

    scenario: MeetingScenario | None
    needs_regeneration: bool


class OpenAIScenarioGenerator:
    """会議録を一度だけ構造化シナリオへ変換するOpenAIアダプター。"""

    model = "gpt-4o"
    CHUNK_SUMMARY_CHARACTERS = 4_000
    MAX_CHUNKS_PER_AGGREGATION = 12

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")

    def generate(
        self,
        meeting: Meeting,
        actors: list[ScenarioActorData],
        source_chunks: list[str],
    ) -> dict[str, Any]:
        """一次発言を根拠に、再生用のJSONシナリオを一度だけ生成する。"""
        if not self.api_key:
            raise ScenarioGenerationError("OPENAI_API_KEY is not configured.")

        client = OpenAI(api_key=self.api_key)
        source_chunks = self._summarize_source_chunks(client, source_chunks)
        content = self._request_json_content(
            client,
            [
                {
                    "role": "system",
                    "content": (
                        "あなたは国会会議録を題材にした教育用シミュレーションゲームの"
                        "シナリオ編集者です。実在人物が実際に発言したかのようには書かず、"
                        "与えられた一次資料に基づくシミュレーションであることを守ってください。"
                        "根拠にない事実を作らず、actor_key と evidence_speech_order は必ず"
                        "入力にある値を使ってください。各ターンには選択肢を必ず二つ作り、"
                        "適切な選択を一つだけ指定してください。入力された全アクターを"
                        "必ず登場させるのではなく、会議を進めるうえで重要なアクターを選んでください。"
                        "選んだアクターには少なくとも一つのターンを割り当ててください。"
                        "Return valid json only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "会議録を役割選択・二択進行型ゲームシナリオにする",
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
                                "background": "string",
                                "success_label": "string",
                                "failure_label": "string",
                                "judgment_criteria": "string",
                                "passing_score": "0-100 integer",
                                "turns": [
                                    {
                                        "actor_key": "actor key from actors",
                                        "dialogue": "simulation dialogue",
                                        "evidence_speech_order": "source speech order",
                                        "evidence_note": "why this source supports the turn",
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
                                        ],
                                    }
                                ],
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
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

    def _summarize_source_chunks(
        self, client: OpenAI, source_chunks: list[str]
    ) -> list[str]:
        """長い会議録を小さな入力単位で要約し、段階的に集約する。"""
        summaries = [
            self._summarize_chunk(client, source_chunk)
            for source_chunk in source_chunks
        ]
        while len(summaries) > self.MAX_CHUNKS_PER_AGGREGATION:
            summaries = [
                self._summarize_chunk(client, "\n\n".join(summary_group))
                for summary_group in self._batched(summaries)
            ]
        return summaries

    def _summarize_chunk(self, client: OpenAI, source_chunk: str) -> str:
        """入力単位の発言順・アクター・根拠を失わない短い構造化要約を作る。"""
        content = self._request_json_content(
            client,
            [
                {
                    "role": "system",
                    "content": (
                        "会議録の入力単位を、後段のゲームシナリオ生成に使う短い"
                        "構造化要約へ変換してください。事実を追加せず、speech_order、"
                        "actor_key、source_url を必ず残してください。"
                        "Return valid json only."
                    ),
                },
                {"role": "user", "content": source_chunk},
            ],
        )
        return content[: self.CHUNK_SUMMARY_CHARACTERS]

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
            raise ScenarioGenerationError(
                "The scenario generator request failed."
            ) from error
        content = response.choices[0].message.content
        if not content:
            raise ScenarioGenerationError(
                "The scenario generator returned an empty response."
            )
        return content

    def _batched(self, summaries: list[str]) -> list[list[str]]:
        """集約用の要約を、プロンプト上限を超えない単位に分ける。"""
        return [
            summaries[index : index + self.MAX_CHUNKS_PER_AGGREGATION]
            for index in range(0, len(summaries), self.MAX_CHUNKS_PER_AGGREGATION)
        ]


class ScenarioService:
    """シナリオカセットの生成・再利用と、会議録由来データの正規化を担う。"""

    PROMPT_VERSION = "meeting-simulation-v1"
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
        payload = self._normalize_payload(generated, actors, speeches)
        scenario_actors = [actor for actor in actors if actor.key in payload.actor_keys]
        return self.repository.create_scenario(
            meeting=meeting,
            source_hash=source_hash,
            prompt_version=self.PROMPT_VERSION,
            generator_model=self.generator.model,
            payload=payload,
            actors=scenario_actors,
            speeches_by_order={speech.speech_order: speech for speech in speeches},
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
    def _normalize_payload(
        generated: dict[str, Any],
        actors: list[ScenarioActorData],
        speeches: list[Speech],
    ) -> ScenarioPayload:
        actor_keys = {actor.key for actor in actors}
        speech_orders = {speech.speech_order for speech in speeches}
        raw_turns = generated.get("turns")
        if not isinstance(raw_turns, list):
            raise ScenarioGenerationError("The scenario does not contain turns.")

        turns: list[ScenarioTurnData] = []
        for raw_turn in raw_turns:
            if not isinstance(raw_turn, dict):
                continue
            actor_key = raw_turn.get("actor_key")
            evidence_speech_order = raw_turn.get("evidence_speech_order")
            choices = raw_turn.get("choices")
            dialogue = str(raw_turn.get("dialogue", "")).strip()
            if (
                actor_key not in actor_keys
                or not isinstance(evidence_speech_order, int)
                or evidence_speech_order not in speech_orders
                or not isinstance(choices, list)
                or len(choices) != 2
                or not dialogue
            ):
                continue
            normalized_choices: list[ScenarioChoiceData] = []
            for choice_number, choice in enumerate(choices, start=1):
                if (
                    not isinstance(choice, dict)
                    or not str(choice.get("text", "")).strip()
                ):
                    normalized_choices = []
                    break
                normalized_choices.append(
                    ScenarioChoiceData(
                        choice_number=choice_number,
                        text=str(choice["text"]).strip(),
                        is_correct=bool(choice.get("is_correct")),
                        rationale=str(choice.get("rationale", "")).strip(),
                    )
                )
            if not normalized_choices:
                continue
            correct_choice_index = next(
                (
                    index
                    for index, choice in enumerate(normalized_choices)
                    if choice.is_correct
                ),
                0,
            )
            normalized_choices = [
                replace(choice, is_correct=index == correct_choice_index)
                for index, choice in enumerate(normalized_choices)
            ]
            order_key = f"{actor_key}:{evidence_speech_order}"
            if hashlib.sha256(order_key.encode()).digest()[0] % 2:
                normalized_choices.reverse()
            normalized_choices = [
                replace(choice, choice_number=choice_number)
                for choice_number, choice in enumerate(normalized_choices, start=1)
            ]
            turns.append(
                ScenarioTurnData(
                    turn_number=len(turns) + 1,
                    actor_key=actor_key,
                    dialogue=dialogue,
                    evidence_speech_order=evidence_speech_order,
                    evidence_note=(
                        str(raw_turn.get("evidence_note", "")).strip()
                        or "会議録の発言を根拠にしたターンです。"
                    ),
                    choices=tuple(normalized_choices),
                )
            )
        if not turns:
            raise ScenarioGenerationError("The scenario did not contain valid turns.")
        return ScenarioPayload(
            title=str(generated.get("title") or "会議録シミュレーション").strip(),
            background=str(generated.get("background") or "").strip(),
            success_label=str(generated.get("success_label") or "成立").strip(),
            failure_label=str(generated.get("failure_label") or "不成立").strip(),
            judgment_criteria=str(
                generated.get("judgment_criteria") or "根拠発言に沿った選択を行うこと。"
            ).strip(),
            passing_score=ScenarioService._normalize_passing_score(
                generated.get("passing_score")
            ),
            turns=tuple(turns),
        )

    @staticmethod
    def _normalize_passing_score(value: Any) -> int:
        """LLMのスコア値を0から100までの整数へ正規化する。"""
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError):
            return 50
