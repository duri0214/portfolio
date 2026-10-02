from datetime import date

from ...models import ObservedPerson
from ..repository.affiliation_observation_repository import (
    AffiliationObservationRepository,
)
from ..valueobject.affiliation import (
    AffiliationChartData,
    AffiliationChartRowData,
    AffiliationChartSegmentData,
    AffiliationChartTickData,
    AffiliationPeriodData,
    PoliticianSummaryData,
)


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

    def get_chart(
        self, offset: int = 0, limit: int | None = None, query: str = ""
    ) -> AffiliationChartData | None:
        """氏名・よみで絞った人物の会派観測を共通の横軸で描くデータを返す。"""

        observations_by_person: dict[int, list] = {}
        people_by_id: dict[int, ObservedPerson] = {}
        for observation in self.repository.list_all(query=query):
            observations_by_person.setdefault(observation.person_id, []).append(
                observation
            )
            people_by_id[observation.person_id] = observation.person
        if not observations_by_person:
            return None

        start_date = min(
            observations[0].observed_on
            for observations in observations_by_person.values()
        )
        end_date = max(
            observations[-1].observed_on
            for observations in observations_by_person.values()
        )
        affiliations = sorted(
            {
                period.affiliation_label
                for observations in observations_by_person.values()
                for period in self._periods_for(observations)
            }
        )
        color_indexes = {
            affiliation: index % 10 for index, affiliation in enumerate(affiliations)
        }
        summaries = [
            self._summary_for(people_by_id[person_id], observations)
            for person_id, observations in observations_by_person.items()
        ]
        summaries.sort(
            key=lambda item: (
                -item.affiliation_change_count,
                item.person.name,
                item.person.name_yomi,
            )
        )
        visible_summaries = summaries[offset : offset + limit] if limit else summaries
        rows = tuple(
            self._chart_row(
                summary.person,
                observations_by_person[summary.person.pk],
                start_date,
                end_date,
                color_indexes,
            )
            for summary in visible_summaries
        )
        return AffiliationChartData(
            start_date=start_date,
            end_date=end_date,
            ticks=tuple(self._chart_ticks(start_date, end_date)),
            total_row_count=len(summaries),
            rows=rows,
        )

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

    @classmethod
    def _chart_row(
        cls,
        person: ObservedPerson,
        observations,
        start_date: date,
        end_date: date,
        color_indexes: dict[str, int],
    ) -> AffiliationChartRowData:
        """会派観測期間を、重なりを分離した人物一行分のバーへ変換する。"""

        lane_ends: list[date] = []
        segments = []
        for period in cls._periods_for(observations):
            lane = next(
                (
                    index
                    for index, lane_end in enumerate(lane_ends)
                    if lane_end < period.first_observed_on
                ),
                len(lane_ends),
            )
            if lane == len(lane_ends):
                lane_ends.append(period.last_observed_on)
            else:
                lane_ends[lane] = period.last_observed_on
            left_percent, width_percent = cls._period_position(
                period.first_observed_on,
                period.last_observed_on,
                start_date,
                end_date,
            )
            segments.append(
                AffiliationChartSegmentData(
                    affiliation_label=period.affiliation_label,
                    first_observed_on=period.first_observed_on,
                    last_observed_on=period.last_observed_on,
                    left_percent=left_percent,
                    width_percent=width_percent,
                    color_index=color_indexes[period.affiliation_label],
                    lane=lane,
                )
            )
        return AffiliationChartRowData(
            person=person,
            segments=tuple(segments),
            lane_count=len(lane_ends),
        )

    @staticmethod
    def _period_position(
        first_observed_on: date,
        last_observed_on: date,
        start_date: date,
        end_date: date,
    ) -> tuple[float, float]:
        """観測期間を横軸全体に対する左位置と幅へ換算する。"""

        total_days = max((end_date - start_date).days, 1)
        left_percent = ((first_observed_on - start_date).days / total_days) * 100
        width_percent = max(
            ((last_observed_on - first_observed_on).days / total_days) * 100,
            0.8,
        )
        return round(left_percent, 3), round(min(width_percent, 100 - left_percent), 3)

    @staticmethod
    def _chart_ticks(
        start_date: date, end_date: date
    ) -> list[AffiliationChartTickData]:
        """横軸の開始日・年初・終了日から目盛りを組み立てる。"""

        tick_dates = [start_date]
        for year in range(start_date.year + 1, end_date.year + 1):
            tick_date = date(year, 1, 1)
            if tick_date < end_date:
                tick_dates.append(tick_date)
        if end_date != start_date:
            tick_dates.append(end_date)
        total_days = max((end_date - start_date).days, 1)
        return [
            AffiliationChartTickData(
                label=(
                    tick_date.strftime("%Y")
                    if tick_date.month == 1 and tick_date.day == 1
                    else tick_date.isoformat()
                ),
                left_percent=round(
                    ((tick_date - start_date).days / total_days) * 100, 3
                ),
            )
            for tick_date in tick_dates
        ]
