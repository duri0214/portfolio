from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.db.models import Max

from ...models import (
    Meeting,
    MeetingScenario,
    ScenarioActor,
    ScenarioChoice,
    ScenarioPlay,
    ScenarioPlayAnswer,
    ScenarioTurn,
    Speech,
)
from ..valueobject.meeting import MEETING_METADATA_SPEAKER_NAME
from ..valueobject.scenario import (
    ScenarioActorData,
    ScenarioChoiceData,
    ScenarioPayload,
)


class ScenarioRepository:
    """会議録シナリオとゲームプレイを永続化するリポジトリ。"""

    def get_meeting_speeches(self, meeting: Meeting) -> list[Speech]:
        """シナリオ生成に使う発言を時系列で取得する。"""
        return list(
            meeting.speeches.exclude(
                speaker_name=MEETING_METADATA_SPEAKER_NAME
            ).order_by("speech_order", "pk")
        )

    def get_latest_scenario(self, meeting: Meeting) -> MeetingScenario | None:
        """会議録に紐づく最新の利用可能なシナリオを取得する。"""
        return (
            MeetingScenario.objects.filter(
                meeting=meeting, status=MeetingScenario.Status.READY
            )
            .prefetch_related("actors")
            .order_by("-version")
            .first()
        )

    def get_reusable_scenario(
        self, meeting: Meeting, source_hash: str, prompt_version: str
    ) -> MeetingScenario | None:
        """同じ会議録・元データ・プロンプトの保存済みシナリオを取得する。"""
        return (
            MeetingScenario.objects.filter(
                meeting=meeting,
                source_hash=source_hash,
                prompt_version=prompt_version,
                status=MeetingScenario.Status.READY,
            )
            .prefetch_related("actors")
            .order_by("-version")
            .first()
        )

    def get_scenario(self, scenario_id: int) -> MeetingScenario:
        """アクターを含むシナリオを取得する。"""
        return (
            MeetingScenario.objects.select_related("meeting")
            .prefetch_related("actors")
            .get(pk=scenario_id, status=MeetingScenario.Status.READY)
        )

    def create_scenario(
        self,
        meeting: Meeting,
        source_hash: str,
        prompt_version: str,
        generator_model: str,
        payload: ScenarioPayload,
        actors: Iterable[ScenarioActorData],
        speeches: Iterable[Speech],
    ) -> MeetingScenario:
        """新しいバージョンのシナリオ、全アクター、全発言ターンを保存する。"""
        actor_list = list(actors)
        with transaction.atomic():
            latest_version = MeetingScenario.objects.filter(meeting=meeting).aggregate(
                latest=Max("version")
            )["latest"]
            scenario = MeetingScenario.objects.create(
                meeting=meeting,
                version=(latest_version or 0) + 1,
                source_hash=source_hash,
                prompt_version=prompt_version,
                generator_model=generator_model,
                title=payload.title,
                overview=payload.overview,
                success_label=payload.success_label,
                failure_label=payload.failure_label,
                judgment_criteria=payload.judgment_criteria,
                passing_score=payload.passing_score,
            )
            ScenarioActor.objects.bulk_create(
                [
                    ScenarioActor(
                        scenario=scenario,
                        display_order=actor.display_order,
                        name=actor.name,
                        role=actor.role,
                        affiliation=actor.affiliation,
                        speech_count=actor.speech_count,
                    )
                    for actor in actor_list
                ]
            )
            saved_actors_by_identity = {
                (actor.name, actor.role, actor.affiliation): actor
                for actor in ScenarioActor.objects.filter(scenario=scenario)
            }
            for turn_number, speech in enumerate(
                sorted(speeches, key=lambda item: item.speech_order),
                start=1,
            ):
                actor = saved_actors_by_identity[
                    (
                        speech.speaker_name,
                        speech.speaker_role or "",
                        speech.speaker_affiliation or "",
                    )
                ]
                ScenarioTurn.objects.create(
                    scenario=scenario,
                    turn_number=turn_number,
                    actor=actor,
                    dialogue=speech.speech_text,
                    evidence_speech=speech,
                    evidence_note=f"議事録 No.{speech.speech_order} の発言です。",
                )
        return scenario

    @staticmethod
    def get_overview_dialogue(scenario_id: int) -> str | None:
        """二択生成の文脈に使う会議全体要約を取得する。"""
        return (
            MeetingScenario.objects.filter(pk=scenario_id)
            .values_list("overview", flat=True)
            .first()
        )

    def create_play(self, scenario: MeetingScenario, actor_id: int) -> ScenarioPlay:
        """担当アクターを選んだ新規プレイを開始する。"""
        try:
            actor = ScenarioActor.objects.get(pk=actor_id, scenario=scenario)
        except ScenarioActor.DoesNotExist as error:
            raise ValueError("The selected actor is invalid.") from error
        return ScenarioPlay.objects.create(
            scenario=scenario,
            selected_actor=actor,
            next_turn_number=1,
        )

    def get_play(self, play_id: str) -> ScenarioPlay:
        """ゲーム画面・結果画面に必要な関連データをまとめて取得する。"""
        return (
            ScenarioPlay.objects.select_related(
                "scenario", "scenario__meeting", "selected_actor"
            )
            .prefetch_related(
                "scenario__turns__actor",
                "scenario__turns__evidence_speech",
                "scenario__turns__choices",
                "answers__turn",
                "answers__choice",
            )
            .get(play_id=play_id)
        )

    def get_locked_play(self, play_id: str) -> ScenarioPlay:
        """更新中のプレイをロックし、進行に必要な関連を取得する。"""
        return (
            ScenarioPlay.objects.select_for_update()
            .select_related("scenario", "selected_actor")
            .get(play_id=play_id)
        )

    def get_turn(self, scenario_id: int, turn_number: int) -> ScenarioTurn | None:
        """指定したシナリオのターンと選択肢を取得する。"""
        return (
            ScenarioTurn.objects.select_related("actor", "evidence_speech")
            .prefetch_related("choices")
            .filter(scenario_id=scenario_id, turn_number=turn_number)
            .first()
        )

    @staticmethod
    def get_turn_choices(
        turn: ScenarioTurn,
        play: ScenarioPlay | None = None,
        prompt_version: str | None = None,
    ) -> list[ScenarioChoice]:
        """ターンに紐づく選択肢を表示順で取得する。"""
        choices = ScenarioChoice.objects.filter(turn=turn)
        if play is not None:
            choices = choices.filter(play=play)
        if prompt_version is not None:
            choices = choices.filter(prompt_version=prompt_version)
        return list(choices.order_by("choice_number"))

    @staticmethod
    def create_turn_choices(
        play: ScenarioPlay,
        turn: ScenarioTurn,
        choices: Iterable[ScenarioChoiceData],
        prompt_version: str,
    ) -> None:
        """プレイ中に生成した二択をターンへ保存する。"""
        ScenarioChoice.objects.bulk_create(
            [
                ScenarioChoice(
                    play=play,
                    turn=turn,
                    choice_number=choice.choice_number,
                    text=choice.text,
                    is_correct=choice.is_correct,
                    rationale=choice.rationale,
                    prompt_version=prompt_version,
                )
                for choice in choices
            ]
        )

    @staticmethod
    def get_last_turn_number(scenario_id: int) -> int:
        """シナリオの最終ターン番号を返す。"""
        return (
            ScenarioTurn.objects.filter(scenario_id=scenario_id).aggregate(
                last=Max("turn_number")
            )["last"]
            or 0
        )

    @staticmethod
    def create_play_answer(
        play: ScenarioPlay, turn: ScenarioTurn, choice: ScenarioChoice
    ) -> None:
        """選択済みの回答を永続化する。"""
        ScenarioPlayAnswer.objects.create(play=play, turn=turn, choice=choice)

    @staticmethod
    def save_play(play: ScenarioPlay, update_fields: list[str]) -> None:
        """更新されたプレイ状態を永続化する。"""
        play.save(update_fields=update_fields)
