import re
import urllib.request

from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from bs4 import BeautifulSoup
from django.db.models import QuerySet
from django.utils.datetime_safe import datetime
from django.utils.timezone import now, localtime

from vietnam_research.models import Symbol, Industry, Market, IndClass
from vietnam_research.service import log_writter


def retrieve_transaction_date(target_text: str) -> datetime:
    """
    vietkabuの登録日をdatetimeに変換する

    Args:
        target_text: ホーチミン証取株価（2019/08/16 15:00VNT）

    Returns: 2019-08-16 15:00:00
    """
    extracted = re.search('(?<=（).*?(?=VNT）)', target_text)
    if not extracted:
        raise ValueError('想定されたテキストが入力されませんでした（カッコのないテキスト）')

    return datetime.strptime(f"{extracted.group()}:00", '%Y/%m/%d %H:%M:%S')


def extract_newcomer(soup: BeautifulSoup, compare_m_symbol: QuerySet) -> list:
    """
    vietkabuの銘柄リストから、新規登録しなければならないsymbolのリストをあぶり出す\n
    中央寄せtd（css-class: table_list_center）の[0]にはsymbol情報、[1]には業種が入っている\n
    シンボル名には「＊」がついていることがあるので除外する箇所がある（注意銘柄だと思う）

    Args:
        soup: vietkabuの銘柄リスト（既存シンボルもあるし、新規シンボルもあるかもしれない）
        compare_m_symbol: 例えば 'HOSE' だけに絞った m_symbol（市場ごとに処理するのでマスタにいる「その市場の銘柄」が必要）

    Returns:
        list: [{
            'symbol': 'AAA999'
            'name': 'アンファット・バイオプラスチック',
            'industry': Industry(),
        }, ... ]
    """
    m_ind_class = IndClass.objects.all()
    vietkabu = []
    for tag_tr in soup.find_all('tr', id=True):
        tag_td_string_type = tag_tr.find_all('td', class_='table_list_center')
        if not tag_td_string_type:
            continue
        symbol_code = re.sub("＊", '', tag_td_string_type[0].text.strip())
        company_name = tag_td_string_type[0].a.get('title')
        industry1 = re.sub(r'\[(.+)]', '', tag_td_string_type[1].img.get('title'))
        industry2 = re.search(r'(?<=\[).*?(?=])', tag_td_string_type[1].img.get('title')).group()
        try:
            ind_class = m_ind_class.get(industry1=industry1, industry2=industry2)
        except ObjectDoesNotExist:
            log_writter.batch_information(f"{industry1}[{industry2}] が業種マスタに存在しないため {symbol_code} が処理対象外になりました")
            continue
        vietkabu.append({
            'symbol': symbol_code,
            'name': company_name,
            'industry': ind_class
        })
    symbols = {
        "vietkabu": set([x["symbol"] for x in vietkabu]),
        "m_symbol": set([x['code'] for x in compare_m_symbol.values('code')])
    }
    newcomer_symbols = list(symbols["vietkabu"].difference(symbols["m_symbol"]))

    return [x for x in vietkabu if x["symbol"] in newcomer_symbols]


class Command(BaseCommand):
    help = 'industry from viet-kabu'

    def handle(self, *args, **options):
        """
        viet-kabuから株価情報（シンボル・業種・計数）を取得してIndustryテーブルを整備\n
        中央寄せtd（css-class: table_list_center）の[0]にはsymbol情報、[1]には業種が入っている\n
        右寄せtd（css-class: table_list_right）には計数が入っている

        See Also: https://www.viet-kabu.com/stock/hcm.html
        See Also: https://www.viet-kabu.com/stock/hn.html
        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """
        market_list = [
            {"url": 'https://www.viet-kabu.com/stock/hcm.html', "mkt": 'HOSE'},
            {"url": 'https://www.viet-kabu.com/stock/hn.html', "mkt": 'HNX'}
        ]

        m_market = Market.objects.all()
        for processing in market_list:
            print(processing)
            m_symbol = Symbol.objects.filter(market__code=processing['mkt'])
            soup = BeautifulSoup(urllib.request.urlopen(processing['url']).read(), 'lxml')

            # extract transaction date
            tag_th_string_type = soup.find('th', class_='table_list_left')
            transaction_date = retrieve_transaction_date(tag_th_string_type.text.strip())

            # delete records on transaction date
            Industry.objects \
                .filter(recorded_date=transaction_date) \
                .filter(symbol__market__code=processing['mkt']) \
                .delete()

            # register if the symbols to be processed is new
            add_records = []
            for newcomer in extract_newcomer(soup, m_symbol):
                add_records.append(Symbol(
                    code=newcomer['symbol'],
                    name=newcomer['name'],
                    ind_class=newcomer['industry'],
                    market=m_market.get(code=processing['mkt'])
                ))
                log_writter.batch_information(f"{newcomer['symbol']} {newcomer['name']} を追加しました")
            if len(add_records) > 0:
                Symbol.objects.bulk_create(add_records)

            add_records = []
            for tag_tr in soup.find_all('tr', id=True):
                tag_td_string_type = tag_tr.find_all('td', class_='table_list_center')
                if not tag_td_string_type:
                    continue

                # check if it exists in the symbol master
                symbol_code = None
                try:
                    symbol_code = re.sub("＊", '', tag_td_string_type[0].text.strip())
                    symbol = m_symbol.get(code=symbol_code)
                except ObjectDoesNotExist:
                    log_writter.batch_information(f"{symbol_code}がシンボルマスタに存在しないため処理対象外になりました")
                    continue

                tag_td_number_type = tag_tr.find_all('td', class_='table_list_right')
                add_records.append(Industry(
                    recorded_date=transaction_date,
                    open_price=float(tag_td_number_type[2].text),
                    high_price=float(tag_td_number_type[3].text),
                    low_price=float(tag_td_number_type[4].text),
                    closing_price=float(tag_td_number_type[1].text),
                    volume=float(tag_td_number_type[7].text.replace('-', '0').replace(',', '')),
                    trade_price_of_a_day=float(tag_td_number_type[8].text.replace('-', '0').replace(',', '')),
                    marketcap=float(tag_td_number_type[10].text.replace('-', '0').replace(',', '')),
                    per=float(tag_td_number_type[11].text.replace('-', '0')),
                    created_at=localtime(now()).strftime('%Y-%m-%d %a %H:%M:%S'),
                    symbol=symbol
                ))
            if len(add_records) > 0:
                print([x.symbol.code for x in add_records])
                Industry.objects.bulk_create(add_records)
            log_writter.batch_is_done(len(add_records))
