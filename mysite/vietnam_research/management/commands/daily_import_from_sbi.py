import logging
import os
import re
import urllib.request
from pathlib import Path

from django.core.management import BaseCommand
from bs4 import BeautifulSoup
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage

from mysite.settings import BASE_DIR
from vietnam_research.domain.service.logservice import LogService
from vietnam_research.models import Sbi, Symbol


def process_the_text(text_in_pdf: str):
    """
    convert_pdf_to_text をつかって生成された text を加工

    Args:
        text_in_pdf:
    """
    pos = text_in_pdf.find('【ベトナム】') + len('【ベトナム】')
    text_in_pdf = text_in_pdf[pos:]
    text_in_pdf = text_in_pdf.replace('\n', '')
    pos = text_in_pdf.find('【インドネシア】')
    text_in_pdf = text_in_pdf[:pos - 1]
    text_in_pdf = text_in_pdf.replace('▼指数チャート', '')
    pos = text_in_pdf.find('    ')
    text_in_pdf = text_in_pdf[:pos - 1]
    text_in_pdf = re.sub(r'(,\d{4}).*', '', text_in_pdf)

    return f"新興国ウィークリーレポート<br>{text_in_pdf}"


def weekly_topics_us():
    """
    sbi米国株サイトから「今週の注目ポイント」をスクレイピングします

    Returns: TODO: 未実装

    """
    url = 'https://site3.sbisec.co.jp/ETGate/?OutSide=on&_ControlID=WPLETmgR001Control&' \
          '_DataStoreID=DSWPLETmgR001Control&burl=search_foreign&cat1=foreign&cat2=us&dir=us%2F&' \
          'file=foreign_us_01.html&getFlg=on&'
    print(url)

    # soup
    soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')

    li_list = []
    for ul in soup.find_all('ul', class_='md-l-box-menu-link-list md-l-text-sz-01 md-l-list-01'):
        for li in ul.find_all('li'):
            if li and li.string is not None:
                temp = li.string.replace('\n', '').replace('\r', '').replace('　', '')
                if len(temp) > 0:
                    li_list.append(temp)
    print('\n'.join(li_list))


class Command(BaseCommand):
    help = 'symbol from sbi'

    def handle(self, *args, **options):
        """
        Part1: sbi証券からベトナム株式取扱銘柄一覧を取得します <div class="accTbl01"> の <tr> を取得する。\n
        Part2: sbi証券から新興国ウィークリーレポートをpdfで取得したあとテキストに変換します
        Part3:

        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """
        # |Part1
        url = 'https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_vn_list.html'
        soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')

        # delete records on transaction date
        Sbi.objects.all().delete()

        m_symbol = Symbol.objects.filter(market__in=[1, 2])
        tag_tr = soup.find(class_="accTbl01").tbody.find_all("tr")
        sbis = [Sbi(symbol_id=m_symbol.get(code=x.th.p.string).id) for x in tag_tr]

        caller_file_name = Path(__file__).stem
        log_service = LogService('./result.log')

        # insert
        Sbi.objects.bulk_create(sbis)
        log_service.write(f'{caller_file_name} is done.({len(sbis)})')

        # |Part2
        work_folder = Path(BASE_DIR) / 'vietnam_research/static/vietnam_research/sbi_topics'
        if not os.path.exists(work_folder):
            os.makedirs(work_folder)

        # download pdf from sbi
        base_url = "https://search.sbisec.co.jp/v2/popwin/info/stock/market_report_fo_em_topic.pdf"
        try:
            urllib.request.urlretrieve(base_url, Path(work_folder) / base_url.split("/")[-1])
        except PermissionError:
            logging.warning('download pdf: Could not open file! Please close Pdf. Process was abort.')
            exit()

        # comvert pdf to text
        pdf_path = work_folder / 'market_report_fo_em_topic.pdf'
        txt_path = work_folder / 'market_report_fo_em_topic.txt'
        manager = PDFResourceManager()
        with open(txt_path, "wb") as txt_output:
            with open(pdf_path, 'rb') as pdf_input:
                with TextConverter(manager, txt_output, laparams=LAParams()) as conv:
                    interpreter = PDFPageInterpreter(manager, conv)
                    for page in PDFPage.get_pages(pdf_input):
                        interpreter.process_page(page)

        # manipulate text file
        txt_path = work_folder / 'market_report_fo_em_topic.txt'
        with open(txt_path, encoding='utf-8', mode='r') as txt_input:
            text_in_pdf = txt_input.read()
        with open(txt_path, encoding='utf-8', mode='w') as txt_output:
            txt_output.write(process_the_text(text_in_pdf))

        # weekly_topics_us()
