"""フォーム集積場所"""
from django import forms
from .models import Articles, Watchlist, FinancialResultWatch


class ExchangeForm(forms.Form):
    """為替計算用の入力フォームです"""
    current_balance = forms.IntegerField(
        label='現在の残高(VND)',
        required=True,
    )

    unit_price = forms.IntegerField(
        label='買いたい銘柄の単価(VND)',
        required=True,
    )

    quantity = forms.IntegerField(
        label='買いたい銘柄の口数',
        required=True,
    )


class WatchlistCreateForm(forms.ModelForm):
    """ウォッチリスト登録時の入力フォームです"""

    class Meta:
        model = Watchlist
        fields = ('symbol', 'bought_day', 'stocks_price', 'stocks_count')
        exclude = ('already_has',)


class ArticleForm(forms.ModelForm):
    """いいね記事の入力フォームです"""

    class Meta:
        model = Articles
        fields = ("title", "note")


class FinancialResultsForm(forms.ModelForm):
    """決算データの入力フォームです"""

    class Meta:
        model = FinancialResultWatch
        fields = ('date', 'ticker', 'quarter', 'eps_ok', 'sales_ok', 'guidance_ok', 'eps_unit', 'eps_estimate', 'eps_actual', 'sales_unit', 'sales_estimate', 'sales_actual', 'y_over_y_growth_rate', 'note_url')
