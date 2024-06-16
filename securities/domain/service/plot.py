import datetime
import os
from abc import abstractmethod, ABC
from pathlib import Path

import pandas as pd
import seaborn
from django.db.models import QuerySet
from matplotlib import pyplot as plt, ticker

from securities.domain.repository.plot import PlotRepository
from securities.domain.valueobject.plot import RequestData

COLUMN_COMPANY_NAME = "submitter_name"
COLUMN_INDUSTRY = "submitter_industry"
COLUMN_AVG_SALARY = "avg_salary"
COLUMN_AVG_TENURE = "avg_tenure"
COLUMN_AVG_AGE = "avg_age"
COMMON_FONT = ["IPAexGothic"]


class PlotServiceBase(ABC):
    def __init__(
        self, work_dir: Path, target_period: RequestData, grouping_column: str
    ):
        plt.rcParams["font.family"] = COMMON_FONT
        self.work_dir = work_dir
        if not self.work_dir.exists():
            self.work_dir.mkdir(parents=True, exist_ok=True)
        self._repository = PlotRepository()
        self.clean_data = self._clean(self._get_target_data(target_period))
        self.grouping_column = grouping_column
        self.categorical_labels_dict = self._get_labels_sorted_by_averages(
            self.clean_data
        )

    @abstractmethod
    def _get_target_data(self, target_period: RequestData) -> QuerySet:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def _clean(query: QuerySet) -> pd.DataFrame:
        raise NotImplementedError

    def _get_labels_sorted_by_averages(
        self, clean_data: pd.DataFrame
    ) -> dict[str, list[str]]:
        """
        業種別平均でソートしたラベルを 3種類 取得する\n
        Returns: ['不動産業', 'サービス業', '情報・通信業', '水産・農林業', ... ]
        """

        def _sort_labels_by_column_average(
            _data: pd.DataFrame, sort_on: str
        ) -> list[str]:
            sorted_df = (
                _data.groupby([self.grouping_column], as_index=False)
                .mean()
                .sort_values(sort_on)
            )
            return sorted_df[self.grouping_column].tolist()

        return {
            COLUMN_AVG_SALARY: _sort_labels_by_column_average(
                clean_data, sort_on=COLUMN_AVG_SALARY
            ),
            COLUMN_AVG_TENURE: _sort_labels_by_column_average(
                clean_data, sort_on=COLUMN_AVG_TENURE
            ),
            COLUMN_AVG_AGE: _sort_labels_by_column_average(
                clean_data, sort_on=COLUMN_AVG_AGE
            ),
        }

    def plot_all(self, targets: list[tuple[str, str]]):
        for target_counting_column, title in targets:
            self._plot(target_counting_column=target_counting_column, title=title)

    @abstractmethod
    def _plot(self, target_counting_column: str, title: str):
        raise NotImplementedError

    @staticmethod
    def _configure_plot(title: str):
        # Note: gca() は "get current axes" を意味する
        ax = plt.gca()
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.yaxis.set_ticks_position("left")
        ax.xaxis.set_ticks_position("bottom")
        plt.title(title, fontsize=24)

    @abstractmethod
    def save(self, title: str):
        raise NotImplementedError


class BoxenPlotService(PlotServiceBase):
    def __init__(self, work_dir: Path, target_period):
        super().__init__(work_dir, target_period, COLUMN_INDUSTRY)

    def _get_target_data(self, target_period):
        return self._repository.get_period_data(target_period)

    @staticmethod
    def _clean(query: QuerySet) -> pd.DataFrame:
        return pd.DataFrame(
            list(
                query.values(
                    COLUMN_INDUSTRY,
                    COLUMN_AVG_SALARY,
                    COLUMN_AVG_TENURE,
                    COLUMN_AVG_AGE,
                )
            )
        ).dropna()

    def _plot(
        self,
        target_counting_column: str,
        title: str,
    ):
        plt.figure(figsize=(15, 10))
        seaborn.stripplot(
            x=target_counting_column,
            y=COLUMN_INDUSTRY,
            orient="h",
            data=self.clean_data,
            size=3,
            edgecolor="auto",
            order=self.categorical_labels_dict[target_counting_column],
        )
        ax = seaborn.boxenplot(
            x=target_counting_column,
            y=COLUMN_INDUSTRY,
            hue=COLUMN_INDUSTRY,  # TODO: hueをつけないことがdeprecatedだが、hueをつけると色合いがおかしくなる
            orient="h",
            data=self.clean_data,
            palette="rainbow",
            order=self.categorical_labels_dict[target_counting_column],
        )
        ax.grid(which="major", color="lightgray", ls=":", alpha=0.5)
        ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        plt.xlabel(target_counting_column, fontsize=18)
        plt.ylabel(COLUMN_INDUSTRY, fontsize=16)
        plt.title(title, fontsize=24)
        self._configure_plot(title)
        self.save(title)
        # plt.show()

    def save(self, title: str):
        plt.savefig(self.work_dir / f"boxen_plot_{title}.png")


class BarPlotService(PlotServiceBase):
    def __init__(self, work_dir: Path, target_period):
        super().__init__(work_dir, target_period, COLUMN_COMPANY_NAME)

    def _get_target_data(self, target_period):
        # TODO: 業種はとりあえず "情報・通信業" で固定している（Qiita準拠にするために）
        return self._repository.get_period_data_for_specific_industry(
            target_period, "情報・通信業"
        )

    @staticmethod
    def _clean(query: QuerySet) -> pd.DataFrame:
        return pd.DataFrame(
            list(
                query.values(
                    COLUMN_COMPANY_NAME,
                    COLUMN_AVG_SALARY,
                    COLUMN_AVG_TENURE,
                    COLUMN_AVG_AGE,
                )
            )
        ).dropna()

    def _plot(self, target_counting_column: str, title: str):
        # COLUMN_AVG_SALARY が最も高い上位50の行
        df_sort_by_salary = self.clean_data.sort_values(COLUMN_AVG_SALARY)[-50:]
        df_info_label_list_sort_by_salary = df_sort_by_salary[
            COLUMN_COMPANY_NAME
        ].tolist()
        plt.figure(figsize=(15, 12))
        ax = seaborn.barplot(
            x=COLUMN_COMPANY_NAME,
            y=COLUMN_AVG_SALARY,
            hue=COLUMN_COMPANY_NAME,  # TODO: hueをつけないことがdeprecatedだが、hueをつけると色合いがおかしくなる
            data=self.clean_data,
            palette="rocket",
            order=df_info_label_list_sort_by_salary,
        )
        seaborn.set(style="ticks")
        plt.xticks(rotation=90)
        plt.subplots_adjust(hspace=0.8, bottom=0.35)
        ax.grid(which="major", axis="y", color="lightgray", ls=":", alpha=0.5)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x)))
        )
        plt.xlabel(COLUMN_COMPANY_NAME, fontsize=12)
        plt.ylabel(COLUMN_AVG_SALARY, fontsize=18)
        plt.title("情報・通信業界:平均年間給与TOP50", fontsize=24)
        self._configure_plot(title)
        self.save(title)
        # plt.show()

    def save(self, title: str):
        plt.savefig(self.work_dir / f"bar_plot_{title}.png")


if __name__ == "__main__":
    home_dir = os.path.expanduser("~")

    # plot1: 箱ひげ図
    period = RequestData(
        start_date=datetime.date(2022, 11, 1),
        end_date=datetime.date(2023, 10, 31),
    )
    service = BoxenPlotService(
        work_dir=Path(home_dir, "Downloads/xbrlReport/plot"),
        target_period=period,
    )
    service.plot_all(
        [
            (COLUMN_AVG_SALARY, "業種別平均年間給与額"),
            (COLUMN_AVG_TENURE, "業種別平均勤続年数"),
            (COLUMN_AVG_AGE, "業種別平均年齢"),
        ]
    )

    # plot2: 棒グラフ
    period = RequestData(
        start_date=datetime.date(2022, 11, 1),
        end_date=datetime.date(2023, 10, 31),
    )
    service = BarPlotService(
        work_dir=Path(home_dir, "Downloads/xbrlReport/plot"),
        target_period=period,
    )
    service.plot_all(
        [
            (COLUMN_AVG_SALARY, "業種別平均年間給与額"),
        ]
    )

    print("visualize finish")
