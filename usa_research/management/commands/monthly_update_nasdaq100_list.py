import requests
from bs4 import BeautifulSoup
from datetime import datetime
from django.core.management.base import BaseCommand
from usa_research.models import Nasdaq100Company


class Command(BaseCommand):
    help = "Fetch NASDAQ100 components from TradingView"

    def handle(self, *args, **options):
        """
        NASDAQ100の構成銘柄とその業種情報を取得し、DBを更新します。

        処理の流れ:
        1. TradingViewから構成銘柄一覧とセクター情報を取得 (fetch_from_tradingview)
           - セクター情報を保持している唯一のソース
           - 動的コンテンツのため、取得できる銘柄数が100件に満たない場合がある
        2. 取得件数が100件未満の場合、Slickchartsから全構成銘柄を補完 (fetch_from_slickcharts)
           - Slickchartsはセクター情報を持たないが、銘柄リストの網羅性が高い
        3. 取得した全データをループしてDBに保存 (Nasdaq100Companyモデル)
           - update_or_create を使用
           - Slickchartsからの補完データ（セクター情報なし）で既存のセクター情報を上書きしないよう制御
        """
        self.stdout.write("Fetching NASDAQ100 components...")

        companies = self.fetch_from_tradingview()

        if len(companies) < 100:
            self.stdout.write(
                f"TradingView only returned {len(companies)} items. Trying Slickcharts for missing tickers..."
            )
            slick_companies = self.fetch_from_slickcharts()

            # TradingViewの結果をベースにし、足りないものをSlickchartsで補完
            existing_tickers = {c["ticker"] for c in companies}
            for sc in slick_companies:
                if sc["ticker"] not in existing_tickers:
                    companies.append(sc)

        if not companies:
            self.stderr.write("No companies found.")
            return

        # DB保存
        count = 0
        as_of = datetime.now().date()
        for item in companies:
            # 既存のデータを取得して、セクター情報がある場合は上書きしない（Slickchartsからの補完時）
            defaults = {
                "name": item["name"],
                "source": item["source"],
                "as_of": as_of,
            }
            if item.get("sector"):
                defaults["sector"] = item["sector"]
            if item.get("industry"):
                defaults["industry"] = item["industry"]

            obj, created = Nasdaq100Company.objects.update_or_create(
                ticker=item["ticker"], defaults=defaults
            )
            if created:
                count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {len(companies)} companies ({count} new)."
            )
        )

    def fetch_from_tradingview(self):
        url = "https://jp.tradingview.com/symbols/NASDAQ-NDX/components/"
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except Exception as e:
            self.stderr.write(f"Failed to fetch data from TradingView: {e}")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        rows = table.find_all("tr")[1:]
        companies = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 11:
                continue

            # Column 0: Ticker + Name
            ticker_cell = cols[0].find("span", class_="tickerCell-GrtoTeat")
            if not ticker_cell:
                # 念のため古いロジックに近いフォールバックを残す
                ticker_container = cols[0].find("a")
            else:
                ticker_container = ticker_cell

            if not ticker_container:
                continue

            ticker_a = ticker_container.find("a", class_="tickerName-GrtoTeat")
            name_a = ticker_container.find("a", class_="tickerDescription-GrtoTeat")

            if ticker_a and name_a:
                ticker = ticker_a.text.strip()
                name = name_a.text.strip()
            else:
                ticker_sup = ticker_container.find("sup")
                ticker_span = ticker_container.find(
                    "span", class_="tickerName-h_uV989e"
                )

                if ticker_sup:
                    ticker = ticker_sup.text.strip()
                    # 名称は sup を除いた部分
                    # 子要素から NavigableString のみを取得して結合する
                    from bs4.element import NavigableString, Tag

                    name = "".join(
                        [
                            str(child)
                            for child in ticker_container.children
                            if isinstance(child, NavigableString)
                        ]
                    ).strip()
                    # もし NavigableString が空なら、sup以外の要素からテキストを取得
                    if not name:
                        name = "".join(
                            [
                                child.get_text()
                                for child in ticker_container.children
                                if isinstance(child, Tag) and child.name != "sup"
                            ]
                        ).strip()
                elif ticker_span:
                    ticker = ticker_span.text.strip()
                    from bs4.element import NavigableString, Tag

                    name = "".join(
                        [
                            str(child)
                            for child in ticker_container.children
                            if isinstance(child, NavigableString)
                        ]
                    ).strip()
                    if not name:
                        name = "".join(
                            [
                                child.get_text()
                                for child in ticker_container.children
                                if isinstance(child, Tag) and child.name != "span"
                            ]
                        ).strip()
                else:
                    # Use Tag.get_text() explicitly to avoid IDE warnings about PageElement
                    from bs4.element import Tag

                    if isinstance(ticker_container, Tag):
                        # Tag.get_text() supports the separator argument.
                        # Using Tag as a class to call get_text ensures static analyzers recognize the argument.
                        text_val = Tag.get_text(ticker_container, separator="|")
                        full_text = text_val.split("|")
                    else:
                        full_text = ticker_container.text.split("|")

                    if len(full_text) >= 2:
                        ticker = full_text[0].strip()
                        name = full_text[1].strip()
                    else:
                        ticker = ticker_container.text.strip()[:5]  # 仮
                        name = ticker_container.text.strip()

            sector = cols[10].text.strip()

            companies.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "sector": sector,
                    "industry": "",
                    "source": "TradingView",
                }
            )
        return companies

    def fetch_from_slickcharts(self):
        url = "https://www.slickcharts.com/nasdaq100"
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except Exception as e:
            self.stderr.write(f"Failed to fetch data from Slickcharts: {e}")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table", class_="table-borderless")
        if not table:
            table = soup.find("table")

        if not table:
            return []

        rows = table.find_all("tr")[1:]
        companies = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            # Slickcharts structure:
            # 0: Rank
            # 1: Company Name
            # 2: Symbol (Ticker)
            # 3: Weight

            name = cols[1].text.strip()
            ticker = cols[2].text.strip()

            companies.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "sector": "",  # Slickcharts has no sector info
                    "industry": "",
                    "source": "Slickcharts",
                }
            )
        return companies
