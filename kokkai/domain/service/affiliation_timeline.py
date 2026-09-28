from dataclasses import dataclass
from datetime import date

from ...models import ObservedPerson
from ..repository.affiliation_observation_repository import (
    AffiliationObservationRepository,
)


@dataclass(frozen=True)
class PoliticianSummaryData:
    """
    観測対象ごとの会派観測集計。

    Attributes:
        person: 集計対象の、本人確認前の観測対象。
        first_observed_on: 最初に発言会派を観測した日。
        last_observed_on: 最後に発言会派を観測した日。
        observation_count: 人物・日付・会派で重複排除した観測件数。
        speech_count: 観測の根拠になった発言件数。
        affiliation_count: 観測された会派数。会派情報なしも一つの値として数える。
        affiliation_change_count: 日付順の観測値が前の観測と異なった回数。
    """

    person: ObservedPerson
    first_observed_on: date
    last_observed_on: date
    observation_count: int
    speech_count: int
    affiliation_count: int
    affiliation_change_count: int


@dataclass(frozen=True)
class AffiliationPeriodData:
    """
    同じ会派が連続して観測された表示用区間。

    Attributes:
        affiliation: 発言時に観測された会派。空値は会派情報がないことを示す。
        first_observed_on: 区間の最初の観測日。
        last_observed_on: 区間の最後の観測日。
        observations: 区間を構成する会派観測と一次資料根拠。
    """

    affiliation: str
    first_observed_on: date
    last_observed_on: date
    observations: tuple

    @property
    def affiliation_label(self) -> str:
        """未入力の会派情報を、所属なしと断定せずに表示する。"""

        return self.affiliation or "会派情報なし"

    @property
    def observation_count(self) -> int:
        """表示区間に含まれる会派観測の件数を返す。"""

        return len(self.observations)


class AffiliationTimelineService:
    """会派観測を人物単位で集計し、時系列表示用に整える。"""

    def __init__(self, repository: AffiliationObservationRepository | None = None):
        self.repository = repository or AffiliationObservationRepository()

    def list_people(self) -> list[PoliticianSummaryData]:
        """全観測対象の件数・会派数・観測上の変更回数を返す。"""

        summaries = [
            self._summary_for(person) for person in self.repository.list_people()
        ]
        return sorted(
            summaries,
            key=lambda item: (
                -item.affiliation_change_count,
                item.person.name,
                item.person.name_yomi,
            ),
        )

    def get_timeline(
        self, person: ObservedPerson
    ) -> tuple[PoliticianSummaryData, list[AffiliationPeriodData]]:
        """観測対象の集計値と、同会派の連続観測区間を返す。"""

        observations = list(self.repository.list_for_person(person))
        return self._summary_for(person, observations), self._periods_for(observations)

    def _summary_for(
        self, person: ObservedPerson, observations=None
    ) -> PoliticianSummaryData:
        observations = (
            observations
            if observations is not None
            else list(self.repository.list_for_person(person))
        )
        affiliations = {observation.affiliation for observation in observations}
        changes = sum(
            previous.affiliation != current.affiliation
            for previous, current in zip(observations, observations[1:])
        )
        return PoliticianSummaryData(
            person=person,
            first_observed_on=observations[0].observed_on,
            last_observed_on=observations[-1].observed_on,
            observation_count=len(observations),
            speech_count=sum(observation.speech_count for observation in observations),
            affiliation_count=len(affiliations),
            affiliation_change_count=changes,
        )

    @staticmethod
    def _periods_for(observations) -> list[AffiliationPeriodData]:
        periods = []
        for observation in observations:
            if periods and periods[-1].affiliation == observation.affiliation:
                previous = periods[-1]
                periods[-1] = AffiliationPeriodData(
                    affiliation=previous.affiliation,
                    first_observed_on=previous.first_observed_on,
                    last_observed_on=observation.observed_on,
                    observations=(*previous.observations, observation),
                )
            else:
                periods.append(
                    AffiliationPeriodData(
                        affiliation=observation.affiliation,
                        first_observed_on=observation.observed_on,
                        last_observed_on=observation.observed_on,
                        observations=(observation,),
                    )
                )
        return periods
