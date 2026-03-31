import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from django.core.management import BaseCommand

from usa_research.models import Symbol, Market, SbiSymbol


class Command(BaseCommand):
    help = "Import US stock symbols handled by SBI Securities"

    def handle(self, *args, **options):
        """
        SBI証券から米国株取扱銘柄一覧を取得してマスタにします。
        URL: https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_usequity_list.html
        """
        url = "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_usequity_list.html"

        try:
            self.stdout.write(f"Fetching data from {url}...")
            # Use urllib.request as it is used in daily_import_from_sbi.py
            response = urllib.request.urlopen(url)
            soup = BeautifulSoup(response.read(), "lxml")
        except Exception as e:
            self.stderr.write(f"Failed to fetch data: {e}")
            return

        # 既存の SbiSymbol レコードを削除（現在のSBI取扱リストに同期するため）
        SbiSymbol.objects.all().delete()

        # 市場マスタの取得 (NASDAQ: 3, NYSE: 4, NYSE American: 5, NYSE Arca: 6)
        markets = {m.code: m for m in Market.objects.all()}

        # SBIのテーブル構造解析
        # <div class="accTbl01"> 内の <tr> を取得
        tables = soup.find_all(class_="accTbl01")
        if not tables:
            self.stderr.write("No tables with class 'accTbl01' found.")
            return

        sbi_usa_list = []
        new_symbols_count = 0

        for table in tables:
            tag_tr = table.tbody.find_all("tr") if table.tbody else table.find_all("tr")
            for x in tag_tr:
                cols = x.find_all(["th", "td"])
                if len(cols) < 3:
                    continue

                # 0: ティッカー (th p), 1: 銘柄名 (td p), 2: 市場 (td p)
                try:
                    ticker = cols[0].get_text(strip=True)
                    name = cols[1].get_text(strip=True)
                    market_name_raw = cols[2].get_text(strip=True)

                    # 市場名のマッピング
                    market_code = None
                    if "NASDAQ" in market_name_raw.upper():
                        market_code = "NASDAQ"
                    elif "NYSE" in market_name_raw.upper():
                        if "AMERICAN" in market_name_raw.upper():
                            market_code = "NYSE American"
                        elif "ARCA" in market_name_raw.upper():
                            market_code = "NYSE Arca"
                        else:
                            market_code = "NYSE"

                    if not market_code or market_code not in markets:
                        # self.stdout.write(self.style.WARNING(f"Unknown market: {market_name_raw} for {ticker}"))
                        # デフォルトで NYSE にしておくか、スキップするか。ここでは NYSE をデフォルト候補にする
                        market_code = "NYSE" if not market_code else market_code

                    market = markets[market_code]

                    # Symbol の取得または作成
                    symbol, created = Symbol.objects.get_or_create(
                        code=ticker, market=market, defaults={"name": name}
                    )
                    if created:
                        new_symbols_count += 1

                    # SbiSymbol レコードの作成
                    sbi_usa_list.append(SbiSymbol(symbol=symbol))

                except Exception as e:
                    self.stderr.write(f"Error processing row: {e}")
                    continue

        # 一括登録
        SbiSymbol.objects.bulk_create(sbi_usa_list)

        caller_file_name = Path(__file__).stem
        self.stdout.write(
            self.style.SUCCESS(
                f"{caller_file_name} is done. (New Symbols: {new_symbols_count}, Total SBI USA: {len(sbi_usa_list)})"
            )
        )
