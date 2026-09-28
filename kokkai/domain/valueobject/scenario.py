from dataclasses import dataclass

from ...models import MeetingScenario


@dataclass(frozen=True)
class ScenarioAvailability:
    """
    会議詳細に表示するシナリオの利用可否。

    Attributes:
        scenario: 表示対象の最新シナリオ。未生成時はNone。
        needs_regeneration: 会議録の更新により再生成が必要かどうか。
    """

    scenario: MeetingScenario | None
    needs_regeneration: bool


@dataclass(frozen=True)
class ScenarioActorData:
    """
    保存前のシナリオ登場アクターを表す値。

    Attributes:
        key: 生成結果からアクターを参照する一時キー。
        display_order: シナリオ内での表示順。
        name: 発言者名。
        role: 発言者の役割。
        affiliation: 発言者の所属会派。
        speech_count: 元会議録での発言数。
    """

    key: str
    display_order: int
    name: str
    role: str
    affiliation: str
    speech_count: int

    @property
    def identity(self) -> tuple[str, str, str]:
        """同一人物を特定する発言者・役割・所属の組み合わせを返す。"""
        return self.name, self.role, self.affiliation

    def to_prompt_value(self) -> dict[str, str | int]:
        """シナリオ生成APIに渡すアクター情報を返す。"""
        return {
            "key": self.key,
            "display_order": self.display_order,
            "name": self.name,
            "role": self.role,
            "affiliation": self.affiliation,
            "speech_count": self.speech_count,
        }


@dataclass(frozen=True)
class ScenarioChoiceData:
    """
    保存前の二択の選択肢を表す値。

    Attributes:
        choice_number: ターン内の表示順。
        text: 選択肢の本文。
        is_correct: 根拠発言に沿う選択かどうか。
        rationale: 判定の根拠。
    """

    choice_number: int
    text: str
    is_correct: bool
    rationale: str


@dataclass(frozen=True)
class ScenarioPayload:
    """
    保存前の会議録シナリオ全体を表す値。

    Attributes:
        title: シナリオのタイトル。
        overview: 会議全体の要約。
        success_label: 成功時の表示名。
        failure_label: 失敗時の表示名。
        judgment_criteria: 成否の判定基準。
        passing_score: 成功に必要な正答率。
    """

    title: str
    overview: str
    success_label: str
    failure_label: str
    judgment_criteria: str
    passing_score: int
