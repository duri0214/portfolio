import datetime
import urllib.request

import requests
from bs4 import BeautifulSoup
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from requests import HTTPError

from lib.log_service import LogService
from vietnam_research.domain.service.exchange import ExchangeService
from vietnam_research.domain.valueobject.exchange import UrlScale
from vietnam_research.models import VnIndex, ExchangeRate


class Command(BaseCommand):
    help = "vn-index from bloomberg"

    def handle(self, *args, **options):
        """
        bloombergからvn-indexを取り込みます。<div id="last_last"> の <tr> を取得する。
        過去計数は `https://jp.investing.com/indices/vn-historical-data` からseederにまとめる

        Notes: ベトナムなど一部のレートは x100 などで表示されているので割り戻す `https://www.bloomberg.com/quote/VNDJPY:CUR`

        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """
        log_service = LogService("./result.log")

        url_scales = [
            UrlScale(url="https://www.bloomberg.co.jp/quote/VNDJPY:CUR", scale=100),
            UrlScale(url="https://www.bloomberg.co.jp/quote/VNDUSD:CUR", scale=100000),
            UrlScale(url="https://www.bloomberg.co.jp/quote/JPYVND:CUR", scale=1),
            UrlScale(url="https://www.bloomberg.co.jp/quote/JPYUSD:CUR", scale=1),
            UrlScale(url="https://www.bloomberg.co.jp/quote/USDVND:CUR", scale=1),
            UrlScale(url="https://www.bloomberg.co.jp/quote/USDJPY:CUR", scale=1),
            UrlScale(url="https://www.bloomberg.co.jp/quote/VNINDEX:IND", scale=1),
        ]

        ExchangeRate.objects.all().delete()
        for url_scale in url_scales:
            quote_identifier = url_scale.url.split("/")[-1]
            currency_pair = quote_identifier.split(":")[0]
            index_or_currency = quote_identifier.split(":")[1]

            try:
                response = requests.get(url_scale.url)
                response.raise_for_status()
            except HTTPError as http_err:
                log_service.write(
                    f"HTTPエラーが発生しました: {url_scale.url}, エラー: {http_err}"
                )
                continue
            except Exception as err:
                log_service.write(
                    f"リクエストの送信時にエラーが発生しました: {url_scale.url}, エラー: {err}"
                )
                continue

            html_content = urllib.request.urlopen(url_scale.url).read()
            soup = BeautifulSoup(html_content, "lxml")
            rate = None

            if index_or_currency == "CUR":
                base_cur = currency_pair[:3]
                dest_cur = currency_pair[3:]
                soup_price = soup.find(class_="price")
                if not soup_price:
                    try:
                        # 指定された通貨ペアの逆のレートがExchangeRateモデルに存在する場合
                        rate = ExchangeService.get_rate(base_cur, dest_cur)
                    except ObjectDoesNotExist as e:
                        # 指定された通貨ペア（またはその逆）のレートがExchangeRateモデルに存在しない場合
                        log_service.write(
                            f"Rate for {base_cur} to {dest_cur} does not exist: {e}"
                        )
                        continue
                else:
                    rate = float(soup_price.text.replace(",", "")) / url_scale.scale

                ExchangeRate.objects.create(
                    base_cur_code=base_cur,
                    dest_cur_code=dest_cur,
                    rate=rate,
                )
            elif index_or_currency == "IND":
                transaction_date = datetime.datetime.strptime(
                    soup.find(class_="price-datetime").text.split()[-1], "%Y/%m/%d"
                )
                soup_price = soup.find(class_="price")
                rate = closing_price = soup_price.text.replace(",", "")
                VnIndex.objects.update_or_create(
                    Y=transaction_date.strftime("%Y"),
                    M=transaction_date.strftime("%m"),
                    defaults={"closing_price": closing_price},
                )

            log_service.write(f"データの取得に成功しました: {url_scale.url} {rate}")
