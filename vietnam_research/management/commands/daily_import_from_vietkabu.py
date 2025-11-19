import urllib.request

from bs4 import BeautifulSoup
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from django.utils.timezone import now, localtime
from vietnam_research.domain.valueobject.vietkabu import (
    TransactionDate,
    MarketDataRow,
    MarketDataRowError,
)
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

            # 市場情報の更新日
            transaction_date = TransactionDate(
                th_tag=soup.find("th", class_="table_list_left")
            ).to_date()

            # 当日データがあったら処理しない
            if Industry.objects.filter(
                recorded_date=transaction_date, symbol__market__code=market.code
            ).exists():
                message = f"{market.code}の当日データがあったので処理対象外になりました"
                print(message)
                continue

            tag_trs = [
                tr for tr in soup.find_all("tr", id=True) if tr.get("id") != "trdemo"
            ]

            # MarketDataRow作成時のエラーハンドリング
            market_data_rows = []
            skip_count = 0
            for i, tag_tr in enumerate(tag_trs):
                try:
                    market_data_row = MarketDataRow(tag_tr)
                    market_data_rows.append(market_data_row)
                except MarketDataRowError as e:
                    skip_count += 1
                    debug_message = f"スキップした行 {i}: {str(e)} - データ: {e.get_simplified_html()}"
                    print(debug_message)

            processed_count = 0
            for market_data_row in market_data_rows:
                # STEP1: 業種マスタを引いて
                try:
                    ind_class = m_ind_class.get(
                        industry1=market_data_row.industry1,
                        industry2=market_data_row.industry2,
                    )
                except ObjectDoesNotExist:
                    # 新規業種が出てきたタイミングで登録できないのは m_symbol.industry_class を人間が決める必要があるからです
                    message = f"{market_data_row.industry_title} が業種マスタに存在しないため {market_data_row.code} が処理対象外になりました"
                    print(message)
                    continue

                # STEP2: Symbol table に存在チェック
                if not m_symbol_list.filter(code=market_data_row.code).exists():
                    # 新規の顔ぶれが出たら登録
                    symbol = Symbol.objects.create(
                        code=market_data_row.code,  # AAA
                        name=market_data_row.name,  # アンファット・バイオプラスチック
                        ind_class=ind_class,
                        market=m_market.get(code=market.code),
                    )
                    message = (
                        f"{market_data_row.code} {market_data_row.name} を追加しました"
                    )
                    print(message)
                else:
                    # 既存先でも会社名が変わっていることがある
                    symbol = m_symbol_list.get(code=market_data_row.code)
                    if symbol.name != market_data_row.name:
                        symbol.name = market_data_row.name
                        symbol.save(update_fields=["name"])

                # STEP3: Industry table（計数）
                Industry.objects.create(
                    recorded_date=transaction_date,
                    created_at=localtime(now()).strftime("%Y-%m-%d %a %H:%M:%S"),
                    symbol=symbol,
                    open_price=market_data_row.open_price,
                    high_price=market_data_row.high_price,
                    low_price=market_data_row.low_price,
                    closing_price=market_data_row.closing_price,
                    volume=market_data_row.volume,
                    marketcap=market_data_row.marketcap,
                    per=market_data_row.per,
                )
                processed_count += 1

            total_rows = len(market_data_rows) + skip_count
            final_message = f"{market.code}の処理が完了しました。全{total_rows}件中{processed_count}件が処理されました（スキップ{skip_count}件）"
            print(final_message)
