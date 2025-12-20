import datetime
import requests
from django.core.management import BaseCommand

from vietnam_research.models import VnIndex, ExchangeRate


class Command(BaseCommand):
    help = "Import exchange rates and VN-INDEX from Yahoo Finance"

    def handle(self, *args, **options):
        """
        Yahoo Finance APIから為替レートとVN-INDEXを取得します。
        Bloombergの403エラー対策としてAPI経由に切り替えました。
        """
        headers = {"User-Agent": "Mozilla/5.0"}

        # 為替レートの更新（一旦全削除）
        ExchangeRate.objects.all().delete()

        # 為替レートの取得
        currency_pairs = [
            ("VND", "JPY", "VNDJPY=X"),
            ("VND", "USD", "VNDUSD=X"),
            ("JPY", "VND", "JPYVND=X"),
            ("JPY", "USD", "JPYUSD=X"),
            ("USD", "VND", "USDVND=X"),
            ("USD", "JPY", "USDJPY=X"),
        ]

        for base, dest, symbol in currency_pairs:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                rate = data["chart"]["result"][0]["meta"]["regularMarketPrice"]

                # VNDUSD=X などが 0.0 の場合の補完
                if rate == 0 or rate is None:
                    if base == "VND" and dest == "USD":
                        # USDVNDの逆数を使用
                        url_inv = "https://query1.finance.yahoo.com/v8/finance/chart/USDVND=X"
                        res_inv = requests.get(url_inv, headers=headers, timeout=10)
                        rate_inv = res_inv.json()["chart"]["result"][0]["meta"][
                            "regularMarketPrice"
                        ]
                        if rate_inv and rate_inv != 0:
                            rate = 1 / rate_inv
                        else:
                            raise ValueError(f"Rate for {symbol} is 0 and fallback failed")
                    else:
                        raise ValueError(f"Rate for {symbol} is 0")

                ExchangeRate.objects.create(
                    base_cur_code=base,
                    dest_cur_code=dest,
                    rate=rate,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully fetched {base}{dest}: {rate}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to fetch exchange rate {symbol}: {e}")
                )

        # VN-INDEXの取得 (Investing.com からスクレイピング)
        vn_index_url = "https://jp.investing.com/indices/vn"
        try:
            # 取得用のヘッダー（Investing.comはボット対策が厳しいためブラウザを模倣）
            scrape_headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(vn_index_url, headers=scrape_headers, timeout=10)
            response.raise_for_status()

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "lxml")
            price_element = soup.find(attrs={"data-test": "instrument-price-last"})

            if price_element:
                price_str = price_element.text.replace(",", "")
                closing_price = float(price_str)
                now = datetime.datetime.now()
                VnIndex.objects.update_or_create(
                    Y=now.strftime("%Y"),
                    M=now.strftime("%m"),
                    defaults={"closing_price": closing_price},
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully fetched VN-INDEX: {closing_price}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"VN-INDEX element not found on Investing.com ({vn_index_url})"
                    )
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch VN-INDEX: {e}"))
