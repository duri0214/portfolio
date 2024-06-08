import datetime
import os
from pathlib import Path

import pandas as pd
import seaborn
from django.db.models import QuerySet
from matplotlib import pyplot as plt, ticker

from securities.domain.repository.plot import PlotRepository
from securities.domain.valueobject.plot import RequestData


class PlotService:
    COLUMN_INDUSTRY = "submitter_industry"
    COLUMN_AVG_SALARY = "avg_salary"
    COLUMN_AVG_TENURE = "avg_tenure"
    COLUMN_AVG_AGE = "avg_age"

    def __init__(self, work_dir: Path):
        plt.rcParams["font.family"] = ["IPAexGothic"]
        self.work_dir = work_dir
        if not self.work_dir.exists():
            self.work_dir.mkdir(parents=True, exist_ok=True)
        self.repository = PlotRepository()

    def plot(self, data):
        # TODO: graph_typeをinjectionしたほうがいいのか？
        #  BoxAndWhisker, Bar, KernelDensityEst
        pass

    def save(self, filename: str):
        pass

    @staticmethod
    def clean_data(query: QuerySet) -> pd.DataFrame:
        df = pd.DataFrame(
            list(
                query.values(
                    "avg_salary",
                    "avg_tenure",
                    "avg_age",
                    "number_of_employees",
                    "submitter_industry",
                )
            )
        ).dropna()
        print(f"records: {len(df)}")
        return df

    def get_sorted_labels(
        self, data: pd.DataFrame
    ) -> tuple[list[str], list[str], list[str]]:
        def _sort_and_get_label_list(_data: pd.DataFrame, sort_on: str) -> list[str]:
            sorted_df = (
                _data.groupby([self.COLUMN_INDUSTRY], as_index=False)
                .mean()
                .sort_values(sort_on)
            )
            return sorted_df[self.COLUMN_INDUSTRY].tolist()

        return (
            _sort_and_get_label_list(data, sort_on=self.COLUMN_AVG_SALARY),
            _sort_and_get_label_list(data, sort_on=self.COLUMN_AVG_TENURE),
            _sort_and_get_label_list(data, sort_on=self.COLUMN_AVG_AGE),
        )

    def boxen_plot(
        self,
        target_counting_column: str,
        label_list: list[str],
        df_dropped_dataset: pd.DataFrame,
        title: str,
        file_name: str,
    ):
        plt.figure(figsize=(15, 10))
        seaborn.stripplot(
            x=target_counting_column,
            y=self.COLUMN_INDUSTRY,
            orient="h",
            data=df_dropped_dataset,
            size=3,
            edgecolor="auto",
            order=label_list,
        )
        ax = seaborn.boxenplot(
            x=target_counting_column,
            hue=self.COLUMN_INDUSTRY,
            y=self.COLUMN_INDUSTRY,
            orient="h",
            data=df_dropped_dataset,
            palette="rainbow",
            order=label_list,
        )
        ax.grid(which="major", color="lightgray", ls=":", alpha=0.5)
        ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        plt.xlabel(target_counting_column, fontsize=18)
        plt.ylabel(self.COLUMN_INDUSTRY, fontsize=16)
        plt.title(title, fontsize=24)
        plt.gca().spines["right"].set_visible(False)
        plt.gca().spines["top"].set_visible(False)
        plt.gca().yaxis.set_ticks_position("left")
        plt.gca().xaxis.set_ticks_position("bottom")
        plt.savefig(self.work_dir / file_name)
        plt.show()


if __name__ == "__main__":
    home_dir = os.path.expanduser("~")
    service = PlotService(work_dir=Path(home_dir, "Downloads/xbrlReport/plot"))
    # 給与情報等の各データが全て揃っていない企業は、欠損データとして今回の処理から対象外とする（記事に習う）
    df_cleaned_data = service.clean_data(
        service.repository.get_target_data(
            RequestData(
                start_date=datetime.date(2023, 11, 1),
                end_date=datetime.date(2023, 11, 29),
            )
        )
    )
    label_list_by_salary, label_list_by_service, label_list_by_age = (
        service.get_sorted_labels(df_cleaned_data)
    )

    service.boxen_plot(
        target_counting_column=service.COLUMN_AVG_SALARY,
        label_list=label_list_by_salary,
        df_dropped_dataset=df_cleaned_data,
        title="業種別平均年間給与額",
        file_name="boxen_plot_1.png",
    )
    service.boxen_plot(
        target_counting_column=service.COLUMN_AVG_TENURE,
        label_list=label_list_by_service,
        df_dropped_dataset=df_cleaned_data,
        title="業種別平均勤続年数",
        file_name="boxen_plot_2.png",
    )
    service.boxen_plot(
        target_counting_column=service.COLUMN_AVG_AGE,
        label_list=label_list_by_age,
        df_dropped_dataset=df_cleaned_data,
        title="業種別平均年齢",
        file_name="boxen_plot_3.png",
    )

    # visualize_jointplot(df_cleaned_data)
    # visualize_barplot(df_cleaned_data)
    # print("visualize finish")

    # service.plot()
    # service.save(filename="xxx.png")
