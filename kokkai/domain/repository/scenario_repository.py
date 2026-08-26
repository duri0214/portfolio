from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

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


class ScenarioRepository:
    """会議録シナリオとゲームプレイを永続化するリポジトリ。"""

    def get_meeting_speeches(self, meeting: Meeting) -> list[Speech]:
        """シナリオ生成に使う発言を時系列で取得する。"""
        return list(meeting.speeches.all().order_by("speech_order", "pk"))

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
        payload: dict[str, Any],
        actors: Iterable[dict[str, Any]],
        speeches_by_order: dict[int, Speech],
    ) -> MeetingScenario:
        """新しいバージョンのシナリオ、アクター、ターン、二択をまとめて保存する。"""
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
                title=payload["title"],
                background=payload["background"],
                success_label=payload["success_label"],
                failure_label=payload["failure_label"],
                judgment_criteria=payload["judgment_criteria"],
                passing_score=payload["passing_score"],
            )
            ScenarioActor.objects.bulk_create(
                [
                    ScenarioActor(
                        scenario=scenario,
                        display_order=actor["display_order"],
                        name=actor["name"],
                        role=actor["role"],
                        affiliation=actor["affiliation"],
                        speech_count=actor["speech_count"],
                    )
                    for actor in actor_list
                ]
            )
            saved_actors_by_identity = {
                (actor.name, actor.role, actor.affiliation): actor
                for actor in ScenarioActor.objects.filter(scenario=scenario)
            }
            actors_by_key = {
                actor["key"]: saved_actors_by_identity[
                    (actor["name"], actor["role"], actor["affiliation"])
                ]
                for actor in actor_list
            }

            for turn_data in payload["turns"]:
                turn = ScenarioTurn.objects.create(
                    scenario=scenario,
                    turn_number=turn_data["turn_number"],
                    actor=actors_by_key[turn_data["actor_key"]],
                    dialogue=turn_data["dialogue"],
                    evidence_speech=speeches_by_order[
                        turn_data["evidence_speech_order"]
                    ],
                    evidence_note=turn_data["evidence_note"],
                )
                ScenarioChoice.objects.bulk_create(
                    [
                        ScenarioChoice(
                            turn=turn,
                            choice_number=choice["choice_number"],
                            text=choice["text"],
                            is_correct=choice["is_correct"],
                            rationale=choice["rationale"],
                        )
                        for choice in turn_data["choices"]
                    ]
                )
        return scenario

    def create_play(self, scenario: MeetingScenario, actor_id: int) -> ScenarioPlay:
        """担当アクターを選んだ新規プレイを開始する。"""
        actor = ScenarioActor.objects.get(pk=actor_id, scenario=scenario)
        return ScenarioPlay.objects.create(scenario=scenario, selected_actor=actor)

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

    def advance_play(self, play: ScenarioPlay) -> None:
        """選択を伴わない発言を読み終えたプレイを次のターンへ進める。"""
        with transaction.atomic():
            locked_play = (
                ScenarioPlay.objects.select_for_update()
                .select_related("scenario")
                .get(pk=play.pk)
            )
            self._move_to_next_turn(locked_play)

    def answer_play(self, play: ScenarioPlay, turn_id: int, choice_id: int) -> None:
        """選択肢を保存して得点を更新し、次のターンへ進める。"""
        with transaction.atomic():
            locked_play = (
                ScenarioPlay.objects.select_for_update()
                .select_related("scenario")
                .get(pk=play.pk)
            )
            turn = ScenarioTurn.objects.select_related("scenario").get(pk=turn_id)
            choice = ScenarioChoice.objects.select_related("turn").get(pk=choice_id)
            if locked_play.is_completed:
                raise ValueError("This play has already been completed.")
            if (
                turn.scenario_id != locked_play.scenario_id
                or choice.turn_id != turn.pk
                or turn.turn_number != locked_play.next_turn_number
            ):
                raise ValueError(
                    "The selected choice does not belong to the current turn."
                )

            ScenarioPlayAnswer.objects.create(
                play=locked_play, turn=turn, choice=choice
            )
            locked_play.answer_count += 1
            if choice.is_correct:
                locked_play.score += 1
            locked_play.save(update_fields=["answer_count", "score"])
            self._move_to_next_turn(locked_play)

    def _move_to_next_turn(self, play: ScenarioPlay) -> None:
        last_turn_number = (
            ScenarioTurn.objects.filter(scenario=play.scenario).aggregate(
                last=Max("turn_number")
            )["last"]
            or 0
        )
        if play.next_turn_number >= last_turn_number:
            self._complete_play(play)
            return
        play.next_turn_number += 1
        play.save(update_fields=["next_turn_number"])

    @staticmethod
    def _complete_play(play: ScenarioPlay) -> None:
        score_percentage = (
            (play.score / play.answer_count * 100) if play.answer_count else 0
        )
        is_success = score_percentage >= play.scenario.passing_score
        play.result_label = (
            play.scenario.success_label if is_success else play.scenario.failure_label
        )
        play.result_explanation = (
            f"{play.scenario.judgment_criteria}\n"
            f"正解数: {play.score}/{play.answer_count}（{score_percentage:.0f}%）"
        )
        play.completed_at = timezone.now()
        play.save(update_fields=["result_label", "result_explanation", "completed_at"])
