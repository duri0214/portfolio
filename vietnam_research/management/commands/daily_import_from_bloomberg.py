import datetime
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from django.core.management import BaseCommand

from lib.log_service import LogService
from vietnam_research.models import VnIndex


class Command(BaseCommand):
    help = "vn-index from bloomberg"

    def handle(self, *args, **options):
        """
        bloombergからvn-indexを取り込みます。<div id="last_last"> の <tr> を取得する。
        過去計数は `https://jp.investing.com/indices/vn-historical-data` からseederにまとめる

        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """
        url = "https://www.bloomberg.co.jp/quote/VNINDEX:IND"
        soup = BeautifulSoup(urllib.request.urlopen(url).read(), "lxml")
        transaction_date = datetime.datetime.strptime(
            soup.find(class_="price-datetime").text.split()[-1], "%Y/%m/%d"
        )

        caller_file_name = Path(__file__).stem
        log_service = LogService("./result.log")

        today = datetime.date.today()
        if not VnIndex.objects.filter(
            Y=today.strftime("%Y"), M=today.strftime("%m")
        ).exists():
            VnIndex.objects.create(
                Y=transaction_date.strftime("%Y"),
                M=transaction_date.strftime("%m"),
                closing_price=soup.find(class_="price").text.replace(",", ""),
            )
            log_service.write(f"{caller_file_name} is done.({transaction_date})")
        else:
            log_service.write(f"VNIndexの当月データがあったので処理対象外になりました")
