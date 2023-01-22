from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Sum, F

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from mysite.settings import STATIC_ROOT, BASE_DIR
from vietnam_research.models import Industry


def get_data() -> pd.DataFrame:
    """
    バッチに必要なデータを返します

    Returns:
        DataFrame:
    """
    industry_records = Industry.objects \
        .values('recorded_date', 'ind_class__industry1') \
        .annotate(industry1=F('ind_class__industry1')) \
        .annotate(trade_price_of_a_day=Sum('trade_price_of_a_day') / 1000000) \
        .order_by('recorded_date', 'industry1') \
        .values('recorded_date', 'industry1', 'trade_price_of_a_day')

    return pd.json_normalize(industry_records) \
        .pivot(index='recorded_date', columns='industry1', values='trade_price_of_a_day')


class Command(BaseCommand):
    help = 'plot industry stacked bar chart'

    def handle(self, *args, **options):
        """
        Industryテーブルの業種別積み上げを時系列で表示

        See Also: https://pystyle.info/matplotlib-stacked-bar-chart/#outline__3
        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """

        df = get_data()
        n_rows, n_cols = df.shape
        positions = np.arange(n_rows)
        offsets = np.zeros(n_rows, dtype=df.values.dtype)
        colors = plt.get_cmap("RdYlGn")(np.linspace(0, 1, n_cols))

        fig, ax = plt.subplots()
        ax.set_xticks(positions)
        ax.set_xticklabels(df.index)

        # Thinning of X axis labels.
        first_days = {}
        records = Industry.objects.values('recorded_date').distinct()
        for record in records:
            first_days.setdefault(record['recorded_date'].strftime('%Y-%m'),
                                  record['recorded_date'].strftime('%Y-%m-%d'))
        for label in ax.get_xticklabels():
            label.set_visible(True if label.get_text() in first_days.values() else False)

        # Draw a stacked bar chart
        for i in range(len(df.columns)):
            ax.bar(positions, df.iloc[:, i], bottom=offsets, color=colors[i])
            offsets += df.iloc[:, i]

        plt.gcf().set_size_inches(20, 10)
        plt.xticks(rotation=90)
        plt.subplots_adjust(left=0.05, right=0.95, top=0.95)

        font_path = '/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf'
        if Path.exists(Path(font_path).resolve()):
            # for ubuntu jp font
            plt.legend(loc='upper left', labels=df.columns, prop={"family": "IPAMincho"})
        else:
            plt.legend(loc='upper left', labels=df.columns, prop={"family": "MS Gothic"})

        # png save
        out_path = STATIC_ROOT.resolve() / 'vietnam_research/chart/daily_industry_stacked_bar_chart.png'
        plt.savefig(out_path)
        out_path = BASE_DIR.resolve() / 'vietnam_research/static/vietnam_research/chart/daily_industry_stacked_bar_chart.png'
        plt.savefig(out_path)
