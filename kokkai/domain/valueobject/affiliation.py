from dataclasses import dataclass
from datetime import date

from ...models import ObservedPerson


@dataclass(frozen=True)
class AffiliationImportPage:
    """
    会派観測の一回分の会議録取り込み結果。

    Attributes:
        meeting_count: 今回のAPIページから観測へ反映した会議録数。
        total_meeting_count: 現在の月次期間に含まれる会議録の総数。
        next_record_position: 同じ月次期間で次に取得するAPIレコード位置。
    """

    meeting_count: int
    total_meeting_count: int
    next_record_position: int | None


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

    @property
    def first_observation_id(self) -> int:
        """チャートと詳細で同じ区間を指す先頭観測のIDを返す。"""

        return self.observations[0].pk


@dataclass(frozen=True)
class AffiliationChartSegmentData:
    """
    人物別会派ガントチャートに描画する一つの会派期間。

    Attributes:
        affiliation_label: バーに表示する会派名。
        first_observation_id: 区間の先頭観測ID。詳細画面の絞り込みに使う。
        first_observed_on: バーの開始となる最初の観測日。
        last_observed_on: バーの終了となる最後の観測日。
        left_percent: チャート全体におけるバー左端の位置。
        width_percent: チャート全体におけるバーの幅。
        color_index: 会派名ごとに割り当てた色の番号。
        lane: 同日に異なる会派が観測された場合に重ねないための段。
    """

    affiliation_label: str
    first_observation_id: int
    first_observed_on: date
    last_observed_on: date
    left_percent: float
    width_percent: float
    color_index: int
    lane: int


@dataclass(frozen=True)
class AffiliationChartRowData:
    """
    人物一人分の会派ガントチャート行。

    Attributes:
        person: 行の対象人物。
        segments: 人物に属する会派期間のバー。
        lane_count: 行内で必要なバー段数。
    """

    person: ObservedPerson
    segments: tuple[AffiliationChartSegmentData, ...]
    lane_count: int


@dataclass(frozen=True)
class AffiliationChartTickData:
    """
    会派ガントチャートの日付目盛り。

    Attributes:
        label: 画面に表示する年または日付。
        left_percent: チャート全体における目盛り位置。
    """

    label: str
    left_percent: float


@dataclass(frozen=True)
class AffiliationChartData:
    """
    会派ガントチャート全体の描画データ。

    Attributes:
        start_date: 横軸の開始日。
        end_date: 横軸の終了日。
        ticks: 横軸に表示する目盛り。
        total_row_count: 観測がある人物の総数。
        rows: 人物ごとの会派ガントチャート行。
    """

    start_date: date
    end_date: date
    ticks: tuple[AffiliationChartTickData, ...]
    total_row_count: int
    rows: tuple[AffiliationChartRowData, ...]
