from django.test import TestCase
from django.utils.timezone import now

from vietnam_research.forms import WatchlistCreateForm
from vietnam_research.models import Symbol, IndClass, Market, Industry, ExchangeRate


class FormTests(TestCase):
    def setUp(self):
        Symbol.objects.create(
            code="AAA",
            name="アンファット・バイオプラスチック",
            ind_class=IndClass.objects.create(
                industry1="農林水産業", industry2="天然ゴム", industry_class=1
            ),
            market=Market.objects.create(code="HOSE", name="ホーチミン証券取引所"),
        )

        ExchangeRate.objects.create(
            base_cur_code="JPY",
            dest_cur_code="VND",
            rate=170.55,
        )

    def test_watchlist_form_valid(self):
        """test No.1: 正常な入力を行えばエラーにならない"""
        symbol = Symbol.objects.get(code="AAA")
        params = dict(
            symbol=symbol, bought_day=now(), stocks_price=1000, stocks_count=500
        )
        form = WatchlistCreateForm(params, instance=Industry())
        self.assertTrue(form.is_valid())

    def test_watchlist_form_invalid(self):
        """test No.2: 何も入力しなければエラーになることを検証"""
        params = dict()
        form = WatchlistCreateForm(params, instance=Industry())
        self.assertFalse(form.is_valid())

    def test_exchange_calc(self):
        """
        予算、単価、為替レートを使って購入可能な購入可能な株数を計算するテスト。

        テスト内容:
        - budget (予算): 購入するための資金額（JPY）。
        - unit_price (単価): 株や商品の単価（VND）。
        - rate (為替レート): JPYからVNDへの変換レート。

        期待する挙動:
        - 予算内で購入可能な株数を計算し、結果を確認。
        - 合計計算式として分かりやすく `f-string` 表現で情報を出力。
        """
        # テストデータ
        budget = 100000  # 予算 (JPY)
        unit_price = 100000  # 株の単価 (VND)
        rate = 171.05713308244952  # 固定為替レート (JPY → VND)

        # 1口あたりの金額を計算
        yen_per_unit = unit_price / rate
        print(f"1口あたりの金額 (JPY): {yen_per_unit:.2f}円")

        # 購入可能な株数を計算
        can_be_buy = int(budget / yen_per_unit)

        # 合計計算結果を計算して、理解しやすい表現で出力
        total_spent_yen = can_be_buy * yen_per_unit
        print(
            f"合計金額({total_spent_yen:.1f}円) = 株数({can_be_buy}口) * 1株あたりの金額({yen_per_unit:.2f}円)"
        )

        # 検証: 購入可能な株数が期待値通りか
        expected_can_be_buy = 171  # 計算上、株数171が期待される
        self.assertEqual(can_be_buy, expected_can_be_buy)
