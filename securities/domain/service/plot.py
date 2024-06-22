import datetime
import os
from abc import abstractmethod, ABC
from pathlib import Path

import pandas as pd
import seaborn
from django.db.models import QuerySet
from matplotlib import pyplot as plt, ticker

from securities.domain.repository.plot import PlotRepository
from securities.domain.valueobject.plot import (
    RequestData,
    PlotParams,
    PlotParamsForKDE,
)

COLUMN_COMPANY_NAME = "submitter_name"
COLUMN_INDUSTRY = "submitter_industry"
COLUMN_AVG_SALARY = "avg_salary"
COLUMN_AVG_TENURE = "avg_tenure"
COLUMN_AVG_AGE = "avg_age"
COMMON_FONT = ["IPAexGothic"]


class PlotServiceBase(ABC):
    def __init__(
        self,
        work_dir: Path,
        target_period: RequestData,
        display_title: bool,
        categorical_column: str = None,
    ):
        """
        Args:
            work_dir: 処理対象のフォルダ
            target_period: 期間
            display_title: グラフタイトルとファイル名に使用される
            categorical_column: カテゴリカルラベルを作るための集計列
        """
        plt.rcParams["font.family"] = COMMON_FONT
        self.work_dir = work_dir
        if not self.work_dir.exists():
            self.work_dir.mkdir(parents=True, exist_ok=True)
        self._repository = PlotRepository()
        self.categorical_column = categorical_column
        self.clean_data = self._clean(self._get_target_data(target_period))
        self.display_title = display_title
        if self.categorical_column:
            self.categorical_labels_dict = self._get_labels_sorted_by_averages(
                self.clean_data
            )

    @abstractmethod
    def _get_target_data(self, target_period: RequestData) -> QuerySet:
        raise NotImplementedError

    @abstractmethod
    def _clean(self, query: QuerySet) -> pd.DataFrame:
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
                _data.groupby([self.categorical_column], as_index=False)
                .mean()
                .sort_values(sort_on)
            )
            return sorted_df[self.categorical_column].tolist()

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

    def plot_all(self, plot_params_list: list[PlotParams | PlotParamsForKDE]):
        for plot_params in plot_params_list:
            self._plot(plot_params=plot_params)

    @abstractmethod
    def _plot(self, plot_params: PlotParams | PlotParamsForKDE):
        raise NotImplementedError

    @staticmethod
    def _configure_plot():
        # Note: gca() は "get current axes" を意味する
        ax = plt.gca()
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.yaxis.set_ticks_position("left")
        ax.xaxis.set_ticks_position("bottom")

    @abstractmethod
    def save(self, title: str):
        raise NotImplementedError


class BoxenPlotService(PlotServiceBase):
    def __init__(
        self, work_dir: Path, target_period: RequestData, categorical_column: str
    ):
        super().__init__(
            work_dir=work_dir,
            target_period=target_period,
            display_title=True,
            categorical_column=categorical_column,
        )

    def _get_target_data(self, target_period):
        return self._repository.get_period_data(target_period)

    def _clean(self, query: QuerySet) -> pd.DataFrame:
        return pd.DataFrame(
            list(
                query.values(
                    self.categorical_column,
                    COLUMN_AVG_SALARY,
                    COLUMN_AVG_TENURE,
                    COLUMN_AVG_AGE,
                )
            )
        ).dropna()

    def _plot(self, plot_params: PlotParams):
        plt.figure(figsize=(15, 10))
        seaborn.stripplot(
            x=plot_params.x,
            y=self.categorical_column,
            orient="h",
            data=self.clean_data,
            size=3,
            edgecolor="auto",
            order=self.categorical_labels_dict[plot_params.x],
        )
        ax = seaborn.boxenplot(
            x=plot_params.x,
            y=self.categorical_column,
            hue=self.categorical_column,  # TODO: hueをつけないことがdeprecatedだが、hueをつけると色合いがおかしくなる
            orient="h",
            data=self.clean_data,
            palette="rainbow",
            order=self.categorical_labels_dict[plot_params.x],
        )
        ax.grid(which="major", color="lightgray", ls=":", alpha=0.5)
        ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        plt.xlabel(plot_params.x, fontsize=18)
        plt.ylabel(self.categorical_column, fontsize=16)
        if self.display_title:
            plt.title(plot_params.title, fontsize=24)
        self._configure_plot()
        self.save(plot_params.title)
        # plt.show()

    def save(self, title: str):
        plt.savefig(self.work_dir / f"boxen_plot_{title}.png")


class BarPlotService(PlotServiceBase):
    def __init__(
        self, work_dir: Path, target_period: RequestData, categorical_column: str
    ):
        super().__init__(
            work_dir=work_dir,
            target_period=target_period,
            display_title=True,
            categorical_column=categorical_column,
        )

    def _get_target_data(self, target_period):
        # TODO: 業種はとりあえず "情報・通信業" で固定している（Qiita準拠にするために）
        return self._repository.get_period_data_for_specific_industry(
            target_period, "情報・通信業"
        )

    def _clean(self, query: QuerySet) -> pd.DataFrame:
        return pd.DataFrame(
            list(
                query.values(
                    self.categorical_column,
                    COLUMN_AVG_SALARY,
                    COLUMN_AVG_TENURE,
                    COLUMN_AVG_AGE,
                )
            )
        ).dropna()

    def _plot(self, plot_params: PlotParams):
        # COLUMN_AVG_SALARY が最も高い上位50の行
        df_sort_by_salary = self.clean_data.sort_values(COLUMN_AVG_SALARY)[-50:]
        df_info_label_list_sort_by_salary = df_sort_by_salary[
            self.categorical_column
        ].tolist()
        plt.figure(figsize=(15, 12))
        ax = seaborn.barplot(
            x=self.categorical_column,
            y=plot_params.x,
            hue=self.categorical_column,  # TODO: hueをつけないことがdeprecatedだが、hueをつけると色合いがおかしくなる
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
        plt.xlabel(self.categorical_column, fontsize=12)
        plt.ylabel(COLUMN_AVG_SALARY, fontsize=18)
        if self.display_title:
            plt.title(plot_params.title, fontsize=24)
        self._configure_plot()
        self.save(plot_params.title)
        # plt.show()

    def save(self, title: str):
        plt.savefig(self.work_dir / f"bar_plot_{title}.png")


class KernelDensityEstimationPlotService(PlotServiceBase):
    def __init__(self, work_dir: Path, target_period: RequestData):
        super().__init__(
            work_dir=work_dir,
            target_period=target_period,
            display_title=False,
        )

    def _get_target_data(self, target_period: RequestData) -> QuerySet:
        return self._repository.get_period_data(target_period)

    def _clean(self, query: QuerySet) -> pd.DataFrame:
        return pd.DataFrame(
            list(
                query.values(
                    COLUMN_AVG_SALARY,
                    COLUMN_AVG_TENURE,
                    COLUMN_AVG_AGE,
                )
            )
        ).dropna()

    def _plot(self, plot_params: PlotParamsForKDE):
        seaborn.jointplot(
            x=plot_params.x,
            y=plot_params.y,
            data=self.clean_data,
            kind="kde",
            color=plot_params.color,
        )
        if self.display_title:
            plt.title(plot_params.title, fontsize=24)
        self._configure_plot()
        self.save(plot_params.title)
        # plt.show()

    def save(self, title: str):
        plt.savefig(self.work_dir / f"kernel_density_estimation_plot_{title}.png")


if __name__ == "__main__":
    home_dir = os.path.expanduser("~")
    period = RequestData(
        start_date=datetime.date(2022, 11, 1),
        end_date=datetime.date(2023, 10, 31),
    )

    # plot1: 箱ひげ図
    service = BoxenPlotService(
        work_dir=Path(home_dir, "Downloads/xbrlReport/plot"),
        target_period=period,
        categorical_column=COLUMN_INDUSTRY,
    )
    service.plot_all(
        [
            PlotParams(x=COLUMN_AVG_SALARY, title="業種別平均年間給与額"),
            PlotParams(x=COLUMN_AVG_TENURE, title="業種別平均勤続年数"),
            PlotParams(x=COLUMN_AVG_AGE, title="業種別平均年齢"),
        ]
    )

    # plot2: 棒グラフ
    service = BarPlotService(
        work_dir=Path(home_dir, "Downloads/xbrlReport/plot"),
        target_period=period,
        categorical_column=COLUMN_COMPANY_NAME,
    )
    service.plot_all(
        [PlotParams(x=COLUMN_AVG_SALARY, title="情報・通信業界_平均年間給与TOP50")]
    )

    # plot3: カーネル密度推定
    service = KernelDensityEstimationPlotService(
        work_dir=Path(home_dir, "Downloads/xbrlReport/plot"),
        target_period=period,
    )
    service.plot_all(
        [
            PlotParamsForKDE(
                x=COLUMN_AVG_TENURE,
                y=COLUMN_AVG_SALARY,
                color="#d9f2f8",
                title="平均勤続年数x平均年間給与",
            ),
            PlotParamsForKDE(
                x=COLUMN_AVG_AGE,
                y=COLUMN_AVG_SALARY,
                color="#fac8be",
                title="平均年齢x平均年間給与",
            ),
            PlotParamsForKDE(
                x=COLUMN_AVG_AGE,
                y=COLUMN_AVG_TENURE,
                color="#008000",
                title="平均年齢x平均勤続年数",
            ),
        ]
    )

    print("visualize finish")
