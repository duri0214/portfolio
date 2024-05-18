import os
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from django.db.models import Sum, F, Min, Value, CharField
from django.db.models.functions import Concat, ExtractYear, ExtractMonth
from matplotlib import pyplot as plt

from config.settings import STATIC_ROOT, BASE_DIR
from vietnam_research.domain.service.log import LogService
from vietnam_research.models import Industry


def get_data() -> pd.DataFrame:
    """
    バッチに必要なデータを返します

    Returns:
        DataFrame:
    """
    industry_records = (
        Industry.objects.values("recorded_date", "symbol__ind_class__industry1")
        .annotate(industry1=F("symbol__ind_class__industry1"))
        .annotate(trade_price_of_a_day=Sum("trade_price_of_a_day") / 1000000)
        .order_by("recorded_date", "industry1")
        .values("recorded_date", "industry1", "trade_price_of_a_day")
    )

    return pd.json_normalize(industry_records).pivot(
        index="recorded_date", columns="industry1", values="trade_price_of_a_day"
    )


class Command(BaseCommand):
    help = "plot industry stacked bar chart"

    def handle(self, *args, **options):
        """
        Industryテーブルの業種別積み上げを時系列で表示

        See Also: https://pystyle.info/matplotlib-stacked-bar-chart/#outline__3
        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """

        plt.rcParams["font.family"] = ["Meiryo", "IPAexGothic"]
        df = get_data()
        n_rows, n_cols = df.shape
        positions = np.arange(n_rows)
        offsets = np.zeros(n_rows, dtype=df.values.dtype)
        colors = plt.get_cmap("RdYlGn")(np.linspace(0, 1, n_cols))

        fig, ax = plt.subplots()
        ax.set_xticks(positions)
        ax.set_xticklabels(df.index)

        # Thinning of X axis labels.
        first_days = (
            Industry.objects.annotate(
                year=ExtractYear("recorded_date"),
                month=ExtractMonth("recorded_date"),
                concat=Concat("year", Value("-"), "month", output_field=CharField()),
            )
            .values("concat")
            .annotate(Min("recorded_date"))
            .values("recorded_date__min")
        )
        first_days = [
            x["recorded_date__min"].strftime("%Y-%m-%d") for x in list(first_days)
        ]
        for label in ax.get_xticklabels():
            label.set_visible(True if label.get_text() in first_days else False)

        # Draw a stacked bar chart
        for i in range(len(df.columns)):
            ax.bar(positions, df.iloc[:, i], bottom=offsets, color=colors[i])
            offsets += df.iloc[:, i]

        plt.gcf().set_size_inches(20, 10)
        plt.xticks(rotation=90)
        plt.subplots_adjust(left=0.05, right=0.95, top=0.95)

        font_path = "/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf"
        if Path.exists(Path(font_path).resolve()):
            # for ubuntu jp font
            plt.legend(
                loc="upper left", labels=df.columns, prop={"family": ["IPAMincho", "IPAexGothic"]}
            )
        else:
            plt.legend(
                loc="upper left", labels=df.columns, prop={"family": ["Meiryo", "IPAexGothic"]}
            )

        # png save
        file_name = "daily_industry_stacked_bar_chart.png"
        out_path = STATIC_ROOT.resolve() / "vietnam_research/chart" / file_name
        if not os.path.exists(out_path.parent):
            os.makedirs(out_path.parent)
        plt.savefig(out_path)
        out_path = (
            BASE_DIR.resolve()
            / "vietnam_research/static/vietnam_research/chart"
            / file_name
        )
        if not os.path.exists(out_path.parent):
            os.makedirs(out_path.parent)
        plt.savefig(out_path)

        caller_file_name = Path(__file__).stem
        log_service = LogService("./result.log")
        log_service.write(f"{caller_file_name} is done.")
