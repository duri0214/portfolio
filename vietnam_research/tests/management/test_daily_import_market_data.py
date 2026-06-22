from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from vietnam_research.models import ExchangeRate, VnIndex


class YahooFinanceResponse:
    def __init__(self, price):
        self.price = price

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketPrice": self.price,
                        },
                    },
                ],
            },
        }


def yahoo_finance_response_by_url(vn_index_price):
    prices = {
        "VNDJPY=X": 0.0061,
        "VNDUSD=X": 3.797228023542814e-05,
        "JPYVND=X": 162.51,
        "JPYUSD=X": 0.0062,
        "USDVND=X": 26335.0,
        "USDJPY=X": 161.723,
        "%5EVNINDEX.VN": vn_index_price,
    }

    def response(url, headers=None, timeout=10):
        symbol = url.rsplit("/", maxsplit=1)[-1]
        return YahooFinanceResponse(prices[symbol])

    return response


class TestDailyImportMarketData(TestCase):
    @patch("vietnam_research.management.commands.daily_import_market_data.requests.get")
    def test_imports_exchange_rates_and_vn_index_from_yahoo_finance(
        self, mock_requests_get
    ):
        """
        シナリオ:
        - 入力: Yahoo Finance chart APIが為替6件とVN-INDEXの価格を返す。
        - 処理: daily_import_market_data コマンドを実行する。
        - 期待値: 為替レート6件と当月のVN-INDEX終値がDBに保存される。
        """
        mock_requests_get.side_effect = yahoo_finance_response_by_url(1857.91)
        stdout = StringIO()

        call_command("daily_import_market_data", stdout=stdout)

        self.assertEqual(ExchangeRate.objects.count(), 6)
        self.assertTrue(VnIndex.objects.filter(closing_price=1857.91).exists())
        self.assertIn("Successfully fetched VN-INDEX: 1857.91", stdout.getvalue())
        fetched_urls = [call.args[0] for call in mock_requests_get.call_args_list]
        self.assertIn(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EVNINDEX.VN",
            fetched_urls,
        )

    @patch("vietnam_research.management.commands.daily_import_market_data.requests.get")
    def test_does_not_save_vn_index_when_yahoo_finance_has_no_price(
        self, mock_requests_get
    ):
        """
        シナリオ:
        - 入力: Yahoo Finance chart APIがVN-INDEXの価格としてNoneを返す。
        - 処理: daily_import_market_data コマンドを実行する。
        - 期待値: VN-INDEXは保存されず、価格未取得の警告が出力される。
        """
        mock_requests_get.side_effect = yahoo_finance_response_by_url(None)
        stdout = StringIO()

        call_command("daily_import_market_data", stdout=stdout)

        self.assertEqual(VnIndex.objects.count(), 0)
        self.assertIn("VN-INDEX price not found on Yahoo Finance", stdout.getvalue())
