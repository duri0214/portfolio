import urllib.request
import datetime

from django.core.management import BaseCommand
from bs4 import BeautifulSoup

from vietnam_research.models import VnIndex
from vietnam_research.service import log_writter


class Command(BaseCommand):
    help = 'vn-index from bloomberg'

    def handle(self, *args, **options):
        """
        bloombergからvn-indexを取り込みます。<div id="last_last"> の <tr> を取得する。

        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """
        url = 'https://www.bloomberg.co.jp/quote/VNINDEX:IND'
        soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')
        transaction_date = datetime.datetime.strptime(soup.find(class_="price-datetime").text.split()[-1], '%Y/%m/%d')

        today = datetime.date.today()
        if not VnIndex.objects.filter(Y=today.strftime('%Y'), M=today.strftime('%m')).exists():
            VnIndex.objects.create(
                Y=transaction_date.strftime('%Y'),
                M=transaction_date.strftime('%m'),
                closing_price=soup.find(class_="price").text.replace(',', '')
            )
            log_writter.batch_is_done(1)
        else:
            log_writter.batch_is_done(0)
