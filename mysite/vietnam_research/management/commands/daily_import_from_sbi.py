import urllib.request

from django.core.management import BaseCommand
from bs4 import BeautifulSoup

from vietnam_research.models import Sbi, Symbol
from vietnam_research.service import log_writter


class Command(BaseCommand):
    help = 'symbol from sbi'

    def handle(self, *args, **options):
        """
        sbi証券からベトナム株式取扱銘柄一覧を取得します <div class="accTbl01"> の <tr> を取得する。

        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """
        url = 'https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_vn_list.html'
        soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')

        # delete records on transaction date
        Sbi.objects.all().delete()

        m_symbol = Symbol.objects.filter(market__in=[1, 2])
        tag_tr = soup.find(class_="accTbl01").tbody.find_all("tr")
        sbis = [Sbi(symbol_id=m_symbol.get(code=x.th.p.string).id) for x in tag_tr]

        # insert
        Sbi.objects.bulk_create(sbis)
        log_writter.batch_is_done(len(sbis))
