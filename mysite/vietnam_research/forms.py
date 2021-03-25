"""フォーム集積場所"""
from django import forms
from .models import Articles, WatchList


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


class WatchlistForm(forms.ModelForm):
    """ウォッチリスト登録時の入力フォームです"""

    class Meta:
        model = WatchList
        fields = ('symbol', 'bought_day', 'stocks_price', 'stocks_count')
        exclude = ('already_has',)


class ArticleForm(forms.ModelForm):
    """いいね記事の入力フォームです"""

    class Meta:
        model = Articles
        fields = ("title", "note")
