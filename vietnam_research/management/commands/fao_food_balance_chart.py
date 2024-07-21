import io
import re
import zipfile
from pathlib import Path

import pandas as pd
import requests
from django.core.management.base import BaseCommand

from lib.log_service import LogService
from vietnam_research.models import FaoFoodBalanceRankers


class Command(BaseCommand):
    help = "fao_food_balance_chart"

    def handle(self, *args, **options):
        FaoFoodBalanceRankers.objects.all().delete()
        zip_url = (
            "https://bulks-faostat.fao.org/production/FoodBalanceSheets_E_Asia.zip"
        )
        response = requests.get(zip_url)

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            with z.open("FoodBalanceSheets_E_Asia_NOFLAG.csv") as f:
                df = pd.read_csv(f, encoding="latin1").fillna(0)

        # 水産物の供給量を抽出
        df_filtered = df[
            (df["Item"] == "Fish, Seafood")
            & (df["Element"] == "Food supply quantity (kg/capita/yr)")
        ]

        # 'Y2022' to 2022
        end_year_string = df.columns[-1]
        end_year = int(re.findall(r"\d+", end_year_string)[0])

        # ranking
        fao_food_balance_rankers: list[FaoFoodBalanceRankers] = []
        for year in range(2010, end_year + 1):
            year_column = f"Y{year}"
            df_sorted = df_filtered.sort_values(year_column, ascending=False)
            for i, (_, row) in enumerate(df_sorted.iterrows()):
                fao_food_balance_rankers.append(
                    FaoFoodBalanceRankers(
                        year=year,
                        rank=i + 1,
                        name=row["Area"],
                        item=row["Item"],
                        element=row["Element"],
                        unit=row["Unit"],
                        value=row[year_column],
                    )
                )

        # bulk-insert
        log_service = LogService("./result.log")
        FaoFoodBalanceRankers.objects.bulk_create(fao_food_balance_rankers)
        caller_file_name = Path(__file__).stem
        log_service.write(
            f"{caller_file_name} is done.({len(fao_food_balance_rankers)})"
        )
