from django.db import transaction
from django.utils import timezone

from ...models import MeetingScenario, ScenarioChoice, ScenarioPlay, ScenarioTurn
from ..repository.scenario_repository import ScenarioRepository
from ..valueobject.scenario import ScenarioActorData
from .scenario import (
    OpenAIScenarioGenerator,
    ScenarioGenerationError,
    ScenarioGenerator,
    ScenarioService,
)


class ScenarioPlayError(ValueError):
    """シナリオプレイの進行条件を満たさない場合の例外。"""


class ScenarioPlayService:
    """保存済みシナリオの開始・回答・完了判定を一貫して進行する。"""

    def __init__(
        self,
        repository: ScenarioRepository | None = None,
        generator: ScenarioGenerator | None = None,
    ) -> None:
        self.repository = repository or ScenarioRepository()
        self.generator = generator or OpenAIScenarioGenerator()

    def start(self, scenario: MeetingScenario, actor_id: int) -> ScenarioPlay:
        """担当アクターを選択して新しいプレイを開始する。"""
        return self.repository.create_play(scenario, actor_id)

    def prepare_current_turn(self, play_id: str) -> ScenarioPlay:
        """表示する担当ターンの二択を必要に応じて生成し、プレイを返す。"""
        with transaction.atomic():
            play = self.repository.get_locked_play(play_id)
            if not play.is_completed:
                turn = self.repository.get_turn(play.scenario_id, play.next_turn_number)
                if turn is None:
                    self._complete(play)
                else:
                    self._ensure_choices(play, turn)
        return self.repository.get_play(play_id)

    def progress(
        self, play_id: str, action: str | None, choice_id: str | None
    ) -> ScenarioPlay:
        """現在のターンを回答または自動進行し、更新後のプレイを返す。"""
        with transaction.atomic():
            play = self.repository.get_locked_play(play_id)
            if not play.is_completed:
                turn = self.repository.get_turn(play.scenario_id, play.next_turn_number)
                if turn is None:
                    self._complete(play)
                elif action == "answer":
                    self._ensure_choices(play, turn)
                    choices = self.repository.get_turn_choices(turn)
                    self._answer(play, turn, choices, choice_id)
                elif action == "next":
                    choices = self.repository.get_turn_choices(turn)
                    if turn.actor_id == play.selected_actor_id and choices:
                        raise ScenarioPlayError(
                            "Choose one of the two answers before continuing."
                        )
                    if turn.actor_id == play.selected_actor_id:
                        raise ScenarioPlayError(
                            "The choices for this turn are not ready yet."
                        )
                    self._move_to_next_turn(play)
                    if not play.is_completed:
                        next_turn = self.repository.get_turn(
                            play.scenario_id, play.next_turn_number
                        )
                        self._ensure_choices(play, next_turn)
                elif action == "skip_to_before_player_turn":
                    self._skip_to_before_player_turn(play)
                    if not play.is_completed:
                        next_turn = self.repository.get_turn(
                            play.scenario_id, play.next_turn_number
                        )
                        self._ensure_choices(play, next_turn)
                else:
                    raise ScenarioPlayError("Unknown game action.")

        return self.repository.get_play(play_id)

    def _answer(
        self,
        play: ScenarioPlay,
        turn: ScenarioTurn,
        choices: list[ScenarioChoice],
        choice_id: str | None,
    ) -> None:
        """選択可能なターンの回答を記録し、次のターンへ進める。"""
        if turn.actor_id != play.selected_actor_id or not choices:
            raise ScenarioPlayError(
                "This turn cannot be answered by the selected actor."
            )
        try:
            selected_choice_id = int(choice_id)
        except (TypeError, ValueError) as error:
            raise ScenarioPlayError("The selected choice is invalid.") from error
        choice = next(
            (choice for choice in choices if choice.pk == selected_choice_id), None
        )
        if choice is None:
            raise ScenarioPlayError("The selected choice is invalid.")

        self.repository.create_play_answer(play, turn, choice)
        play.answer_count += 1
        if choice.is_correct:
            play.score += 1
        self.repository.save_play(play, ["answer_count", "score"])
        self._move_to_next_turn(play)
        if not play.is_completed:
            next_turn = self.repository.get_turn(
                play.scenario_id, play.next_turn_number
            )
            self._ensure_choices(play, next_turn)

    def _ensure_choices(self, play: ScenarioPlay, turn: ScenarioTurn | None) -> None:
        """プレイヤー担当ターンにだけ未生成の二択を作る。"""
        if turn is None or turn.actor_id != play.selected_actor_id:
            return
        choices = self.repository.get_turn_choices(turn)
        if choices and all(
            choice.prompt_version == ScenarioService.CHOICE_PROMPT_VERSION
            for choice in choices
        ):
            return
        if choices:
            self.repository.delete_turn_choices(turn)
        if turn.evidence_speech is None or turn.actor is None:
            raise ScenarioGenerationError(
                "The player turn does not have source speech information."
            )

        actor = ScenarioActorData(
            key=f"actor-{turn.actor_id}",
            display_order=turn.actor.display_order,
            name=turn.actor.name,
            role=turn.actor.role,
            affiliation=turn.actor.affiliation,
            speech_count=turn.actor.speech_count,
        )
        overview = self.repository.get_overview_dialogue(play.scenario_id)
        if not overview:
            raise ScenarioGenerationError("The scenario does not have an overview.")
        preceding_turn = (
            self.repository.get_turn(play.scenario_id, turn.turn_number - 1)
            if turn.turn_number > 1
            else None
        )
        generated = self.generator.generate_choices(
            play.scenario.meeting,
            actor,
            turn.evidence_speech,
            overview,
            preceding_speech=(
                preceding_turn.evidence_speech if preceding_turn else None
            ),
        )
        choices = ScenarioService.normalize_choices(
            generated,
            actor.key,
            turn.evidence_speech.speech_order,
        )
        self.repository.create_turn_choices(
            turn, choices, ScenarioService.CHOICE_PROMPT_VERSION
        )

    def _move_to_next_turn(self, play: ScenarioPlay) -> None:
        """最終ターンなら完了し、それ以外なら次のターン番号を保存する。"""
        last_turn_number = self.repository.get_last_turn_number(play.scenario_id)
        if play.next_turn_number >= last_turn_number:
            self._complete(play)
            return
        play.next_turn_number += 1
        self.repository.save_play(play, ["next_turn_number"])

    def _skip_to_before_player_turn(self, play: ScenarioPlay) -> None:
        """担当アクターの次のターン直前まで、非担当アクターのターンを進める。"""
        while not play.is_completed:
            turn = self.repository.get_turn(play.scenario_id, play.next_turn_number)
            if turn is None:
                self._complete(play)
                return
            next_turn = self.repository.get_turn(
                play.scenario_id, play.next_turn_number + 1
            )
            if (
                turn.actor_id == play.selected_actor_id
                or next_turn is None
                or next_turn.actor_id == play.selected_actor_id
            ):
                return
            self._move_to_next_turn(play)

    def _complete(self, play: ScenarioPlay) -> None:
        """回答結果から最終判定を作成してプレイを完了する。"""
        score_percentage = (
            play.score / play.answer_count * 100 if play.answer_count else 0
        )
        is_success = score_percentage >= play.scenario.passing_score
        play.result_label = (
            play.scenario.success_label if is_success else play.scenario.failure_label
        )
        score_summary = (
            f"正解数: {play.score}/{play.answer_count}（{score_percentage:.0f}%）"
        )
        play.result_explanation = f"{play.scenario.judgment_criteria}\n{score_summary}"
        play.completed_at = timezone.now()
        self.repository.save_play(
            play, ["result_label", "result_explanation", "completed_at"]
        )
