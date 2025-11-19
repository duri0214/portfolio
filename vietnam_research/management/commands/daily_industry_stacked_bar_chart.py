import os
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from django.db.models import Sum, F, Min, Value, CharField
from django.db.models.functions import Concat, ExtractYear, ExtractMonth
from matplotlib import pyplot as plt

from config.settings import MEDIA_ROOT
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
        .annotate(marketcap=Sum("marketcap"))
        .order_by("recorded_date", "industry1")
        .values("recorded_date", "industry1", "marketcap")
    )

    return pd.json_normalize(industry_records).pivot(
        index="recorded_date", columns="industry1", values="marketcap"
    )


class Command(BaseCommand):
    help = "plot industry stacked bar chart"

    def handle(self, *args, **options):
        """
        Industryテーブルの業種別積み上げを時系列で表示

        処理内容:
        1. 業種別の時価総額データを取得
        2. 積み上げ棒グラフを生成
        3. X軸ラベルを月初のみ表示するよう調整
        4. 凡例と日本語フォントを設定
        5. PNGファイルとして保存

        Notes:
        - matplotlib.use('Agg'): Anti-Grain Geometry バックエンドを使用
          GUI環境不要でPNGファイル生成に特化したレンダリングエンジン
        - チャートサイズ: 20x10インチで出力

        See Also: https://pystyle.info/matplotlib-stacked-bar-chart/#outline__3
        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """

        matplotlib.use("Agg")  # GUIを使わないバックエンドを指定
        plt.rcParams["font.family"] = "DejaVu Sans"
        df = get_data()

        # Translate industry (column) labels to English for legend
        jp_to_en_industry = {
            "サービス業": "Service Industry",
            "不動産業": "Real Estate Industry",
            "商業": "Commerce / Trade",
            "建設業": "Construction Industry",
            "情報通信業": "Information and Communications Industry",
            "製造業": "Manufacturing Industry",
            "農林水産業": "Agriculture, Forestry and Fisheries Industry",
            "運輸・物流業": "Transportation and Logistics Industry",
            "金融業": "Financial Industry",
            "鉱業": "Mining Industry",
            "電気・ガス業": "Electricity and Gas Industry",
        }
        translated_labels = [
            jp_to_en_industry.get(str(col), str(col)) for col in df.columns
        ]

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

        # Legend with translated English labels
        plt.legend(loc="upper left", labels=translated_labels)

        # png save - MEDIAディレクトリに保存
        file_name = "daily_industry_stacked_bar_chart.png"
        media_path = Path(MEDIA_ROOT) / "vietnam_research" / "charts" / file_name

        # ディレクトリ作成
        media_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存
        plt.savefig(media_path)
        plt.close()

        # 成功メッセージ
        self.stdout.write(self.style.SUCCESS(f"Chart saved to: {media_path}"))

        # 標準出力に出力
        caller_file_name = Path(__file__).stem
        print(f"{caller_file_name} is done. Saved to: {media_path}")
