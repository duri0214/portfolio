import re
import urllib.request

from bs4 import BeautifulSoup
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from django.utils.timezone import now, localtime

from lib.log_service import LogService
from vietnam_research.domain.valueobject.management.vietkabu import TransactionDate
from vietnam_research.domain.valueobject.vietkabu import Company, Counting
from vietnam_research.models import Symbol, Industry, Market, IndClass


class Command(BaseCommand):
    help = "industry from viet-kabu"

    def handle(self, *args, **options):
        """
        viet-kabuから株価情報（シンボル・業種・計数）を取得してIndustryテーブルを整備
        .table_list_center の [0] には `ticker`、[1] には `industry` が入っている
        .table_list_right には計数が入っている

        Notes: シンボル名には「＊」がついていることがあるので除外する（注意銘柄）

        See Also: https://www.viet-kabu.com/stock/hcm.html
        See Also: https://www.viet-kabu.com/stock/hn.html
        See Also: https://docs.djangoproject.com/en/5.1/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/5.1/topics/testing/tools/#topics-testing-management-commands
        """
        log_service = LogService("./result.log")

        m_market = Market.objects.filter(code__in=["HOSE", "HNX"])
        m_ind_class = IndClass.objects.all()
        for market in m_market:
            m_symbol_list = Symbol.objects.filter(market__code=market.code)

            # scraping
            url = f"https://www.viet-kabu.com/stock/{market.url_file_name}.html"
            soup = BeautifulSoup(
                urllib.request.urlopen(url).read(),
                "lxml",
            )

            # 市場情報の更新日: 2019-08-16 17:00:00
            transaction_date = TransactionDate(
                th_tag=soup.find("th", class_="table_list_left")
            ).transaction_date

            # 当日データがあったら処理しない
            if Industry.objects.filter(
                recorded_date=transaction_date, symbol__market__code=market.code
            ).exists():
                message = f"{market.code}の当日データがあったので処理対象外になりました"
                log_service.write(message)
                continue

            processed_count = 0
            denominator = 0
            for tag_tr in soup.find_all("tr", id=True):
                # Part1: Symbol table
                tag_tds_center = tag_tr.find_all("td", class_="table_list_center")
                try:
                    company = Company(
                        code=re.sub("＊", "", tag_tds_center[0].text.strip()),
                        name=tag_tds_center[0].a.get("title"),
                        industry1=re.sub(
                            r"\[(.+)]", "", tag_tds_center[1].img.get("title")
                        ),
                        industry2=re.search(
                            r"(?<=\[).*?(?=])", tag_tds_center[1].img.get("title")
                        ).group(),
                    )
                except IndexError:
                    continue

                try:
                    ind_class = m_ind_class.get(
                        industry1=company.industry1, industry2=company.industry2
                    )
                except ObjectDoesNotExist:
                    # このタイミングでinsertできないのは industry_class が決められないからです
                    ind_name_str = f"{company.industry1}[{company.industry2}]"
                    message = f"{ind_name_str} が業種マスタに存在しないため {company.code} が処理対象外になりました"
                    log_service.write(message)
                    continue

                if not m_symbol_list.filter(code=company.code).exists():
                    symbol = Symbol.objects.create(
                        code=company.code,  # AAA
                        name=company.name,  # アンファット・バイオプラスチック
                        ind_class=ind_class,
                        market=m_market.get(code=market.code),
                    )
                    message = f"{company.code} {company.name} を追加しました"
                    log_service.write(message)
                else:
                    symbol = m_symbol_list.get(code=company.code)
                    if symbol.name != company.name:
                        symbol.name = company.name
                        symbol.save(update_fields=["name"])
                denominator += 1

                # Part2: Industry table
                tag_tds_right: list[Counting] = []
                for td in tag_tr.find_all("td", class_="table_list_right"):
                    try:
                        x = Counting(td.text.strip())
                        tag_tds_right.append(x)
                    except ValueError:
                        continue

                # tag_tds_right は通常13要素だが `-` があるとその分要素が減る
                if not tag_tds_right or len(tag_tds_right) < 13:
                    continue

                Industry.objects.create(
                    recorded_date=transaction_date,
                    open_price=tag_tds_right[2].value,
                    high_price=tag_tds_right[3].value,
                    low_price=tag_tds_right[4].value,
                    closing_price=tag_tds_right[1].value,
                    volume=tag_tds_right[7].value,
                    trade_price_of_a_day=tag_tds_right[8].value,
                    marketcap=tag_tds_right[10].value,
                    per=tag_tds_right[11].value,
                    created_at=localtime(now()).strftime("%Y-%m-%d %a %H:%M:%S"),
                    symbol=symbol,
                )
                processed_count += 1

            message = f"{market.code}の処理が完了しました。全{denominator}件中{processed_count}件が処理されました。"
            log_service.write(message)
