import io
import zipfile

import pandas as pd
import requests
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "fao_food_balance_chart"

    def handle(self, *args, **options):
        """ """
        zip_url = (
            "https://bulks-faostat.fao.org/production/FoodBalanceSheets_E_Asia.zip"
        )
        response = requests.get(zip_url)

        # BytesIOを使ってダウンロードしたバイナリデータをファイルのように扱う
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            with z.open("FoodBalanceSheets_E_Asia_NOFLAG.csv") as f:
                df = pd.read_csv(f, encoding="latin1")

        # DataFrame dfの5行を表示します
        df_filtered = df[
            (df["Item"] == "Fish, Seafood")
            & (df["Element"] == "Food supply quantity (kg/capita/yr)")
        ]
        print(df_filtered.head(5))

        # png save（画像の保存とログへの出力のときに参考にする）
        # file_name = "daily_industry_stacked_bar_chart.png"
        # out_path = STATIC_ROOT.resolve() / "vietnam_research/chart" / file_name
        # if not os.path.exists(out_path.parent):
        #     os.makedirs(out_path.parent)
        # plt.savefig(out_path)
        # out_path = (
        #     BASE_DIR.resolve()
        #     / "vietnam_research/static/vietnam_research/chart"
        #     / file_name
        # )
        # if not os.path.exists(out_path.parent):
        #     os.makedirs(out_path.parent)
        # plt.savefig(out_path)
        #
        # caller_file_name = Path(__file__).stem
        # log_service = LogService("./result.log")
        # log_service.write(f"{caller_file_name} is done.")
