from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Articles, Watchlist, FinancialResultWatch


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class ExchangeForm(forms.Form):
    """為替計算用の入力フォームです"""

    budget = forms.IntegerField(
        label="予算（円）",
        required=True,
        widget=forms.NumberInput(attrs={"tabindex": "1"}),
    )

    unit_price = forms.FloatField(
        label="単価",
        required=True,
        widget=forms.NumberInput(attrs={"tabindex": "2", "step": "0.01"}),
    )


class WatchlistCreateForm(forms.ModelForm):
    """ウォッチリスト登録時の入力フォームです"""

    class Meta:
        model = Watchlist
        fields = ("symbol", "bought_day", "stocks_price", "stocks_count")
        widgets = {
            "symbol": forms.TextInput(attrs={"tabindex": "1"}),
            "bought_day": forms.DateInput(attrs={"tabindex": "2"}),
            "stocks_price": forms.NumberInput(attrs={"tabindex": "3"}),
            "stocks_count": forms.NumberInput(attrs={"tabindex": "4"}),
        }


class ArticleForm(forms.ModelForm):
    """いいね記事の入力フォームです"""

    class Meta:
        model = Articles
        fields = ("title", "note")
        widgets = {
            "title": forms.TextInput(attrs={"tabindex": "1"}),
            "note": forms.Textarea(attrs={"tabindex": "2"}),
        }


class FinancialResultsForm(forms.ModelForm):
    """決算データの入力フォームです"""

    class Meta:
        model = FinancialResultWatch
        fields = (
            "recorded_date",
            "symbol",
            "quarter",
            "eps_ok",
            "sales_ok",
            "guidance_ok",
            "eps_unit",
            "eps_estimate",
            "eps_actual",
            "sales_unit",
            "sales_estimate",
            "sales_actual",
            "y_over_y_growth_rate",
            "note_url",
        )
        widgets = {
            "recorded_date": forms.DateInput(attrs={"tabindex": "1"}),
            "symbol": forms.TextInput(attrs={"tabindex": "2"}),
            "quarter": forms.NumberInput(attrs={"tabindex": "3"}),
            "eps_ok": forms.CheckboxInput(attrs={"tabindex": "4"}),
            "sales_ok": forms.CheckboxInput(attrs={"tabindex": "5"}),
            "guidance_ok": forms.CheckboxInput(attrs={"tabindex": "6"}),
            "eps_unit": forms.TextInput(attrs={"tabindex": "7"}),
            "eps_estimate": forms.NumberInput(attrs={"tabindex": "8"}),
            "eps_actual": forms.NumberInput(attrs={"tabindex": "9"}),
            "sales_unit": forms.NumberInput(attrs={"tabindex": "10"}),
            "sales_estimate": forms.NumberInput(attrs={"tabindex": "11"}),
            "sales_actual": forms.NumberInput(attrs={"tabindex": "12"}),
            "y_over_y_growth_rate": forms.NumberInput(attrs={"tabindex": "13"}),
            "note_url": forms.URLInput(attrs={"tabindex": "14"}),
        }
