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

COLUMN_INDUSTRY = "submitter_industry"
COLUMN_AVG_SALARY = "avg_salary"
COLUMN_AVG_TENURE = "avg_tenure"
COLUMN_AVG_AGE = "avg_age"
COMMON_FONT = ["IPAexGothic"]


class PlotServiceBase(ABC):

    def __init__(self, work_dir: Path, target_period):
        plt.rcParams["font.family"] = COMMON_FONT
        self.work_dir = work_dir
        if not self.work_dir.exists():
            self.work_dir.mkdir(parents=True, exist_ok=True)
        self._repository = PlotRepository()
        self.clean_data = self._clean(self._repository.get_target_data(target_period))
        self.categorical_labels_dict = self._get_labels_sorted_by_averages(
            self.clean_data
        )

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

    @staticmethod
    def _get_labels_sorted_by_averages(
        clean_data: pd.DataFrame,
    ) -> dict[str, list[str]]:
        """
        業種別平均でソートしたラベルを 3種類 取得する\n
        Returns: ['不動産業', 'サービス業', '情報・通信業', '水産・農林業', ... ]
        """

        def _sort_labels_by_column_average(
            _data: pd.DataFrame, sort_on: str
        ) -> list[str]:
            sorted_df = (
                _data.groupby([COLUMN_INDUSTRY], as_index=False)
                .mean()
                .sort_values(sort_on)
            )
            return sorted_df[COLUMN_INDUSTRY].tolist()

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

    @abstractmethod
    def save(self, title: str):
        raise NotImplementedError


class BoxenPlotService(PlotServiceBase):

    def __init__(self, work_dir: Path, target_period):
        super().__init__(work_dir, target_period)

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
            hue=COLUMN_INDUSTRY,
            y=COLUMN_INDUSTRY,
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
        plt.gca().spines["right"].set_visible(False)
        plt.gca().spines["top"].set_visible(False)
        plt.gca().yaxis.set_ticks_position("left")
        plt.gca().xaxis.set_ticks_position("bottom")
        self.save(title)
        # plt.show()

    def save(self, title: str):
        plt.savefig(self.work_dir / f"boxen_plot_{title}.png")


class BarPlotService(PlotServiceBase):
    def _plot(self, target_counting_column: str, title: str):
        pass

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

    # visualize_jointplot(df_clean_data)
    # visualize_barplot(df_clean_data)
    # print("visualize finish")

    # service.plot()
    # service.save(filename="xxx.png")
