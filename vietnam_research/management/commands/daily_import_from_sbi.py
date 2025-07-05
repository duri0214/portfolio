import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from django.core.management import BaseCommand

from lib.log_service import LogService
from vietnam_research.models import Sbi, Symbol


class Command(BaseCommand):
    help = "symbol from sbi"

    def handle(self, *args, **options):
        """
        sbi証券からベトナム株式取扱銘柄一覧を取得してマスタにします <div class="accTbl01"> の <tr> を取得する。\n

        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """
        url = "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_vn_list.html"
        soup = BeautifulSoup(urllib.request.urlopen(url).read(), "lxml")

        # delete records on transaction date
        Sbi.objects.all().delete()

        m_symbol = Symbol.objects.filter(market__in=[1, 2])
        tag_tr = soup.find(class_="accTbl01").tbody.find_all("tr")
        sbi_list = []
        for x in tag_tr:
            try:
                sbi_list.append(Sbi(symbol_id=m_symbol.get(code=x.th.p.string).id))
            except Symbol.DoesNotExist:
                continue

        caller_file_name = Path(__file__).stem
        log_service = LogService("./result.log")

        # insert
        Sbi.objects.bulk_create(sbi_list)
        log_service.write(f"{caller_file_name} is done.({len(sbi_list)})")
