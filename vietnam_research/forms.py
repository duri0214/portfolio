import datetime

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Articles, Watchlist, FinancialResultWatch


class CustomAuthenticationForm(AuthenticationForm):
    """
    Bootstrap 5対応のログインフォーム。
    全ての入力フィールドに 'form-control' クラスを適用します。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class ExchangeForm(forms.Form):
    """
    為替・購入計算シミュレーター用フォーム。
    日本円の予算とベトナムドン(VND)の単価から、購入可能口数を算出するために使用します。
    """

    budget = forms.IntegerField(
        label="予算（円）",
        required=True,
        min_value=0,
        widget=forms.NumberInput(
            attrs={"tabindex": "1", "class": "form-control text-end", "min": "0"}
        ),
    )

    unit_price = forms.FloatField(
        label="単価（VND）",
        required=True,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "tabindex": "2",
                "step": "0.01",
                "class": "form-control text-end",
                "min": "0",
            }
        ),
    )


class WatchlistForm(forms.ModelForm):
    """
    ウォッチリスト銘柄登録・編集用フォーム。
    シンボル、購入日、価格、数量、保有状況を入力します。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            import datetime

            self.fields["bought_day"].initial = datetime.date.today()

    stocks_price = forms.IntegerField(
        label="購入単価",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"tabindex": "3", "class": "form-control text-end", "min": "0"}
        ),
    )
    stocks_count = forms.IntegerField(
        label="数量",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"tabindex": "4", "class": "form-control text-end", "min": "0"}
        ),
    )

    class Meta:
        model = Watchlist
        fields = ("symbol", "bought_day", "stocks_price", "stocks_count", "already_has")
        widgets = {
            "symbol": forms.Select(attrs={"tabindex": "1", "class": "form-select"}),
            "bought_day": forms.DateInput(
                attrs={"tabindex": "2", "class": "form-control", "type": "date"}
            ),
            "already_has": forms.CheckboxInput(
                attrs={"tabindex": "5", "class": "form-check-input"}
            ),
        }


class ArticleForm(forms.ModelForm):
    """
    ユーザー投稿記事作成用フォーム。
    タイトルと投稿内容（分析記事など）を入力します。
    """

    class Meta:
        model = Articles
        fields = ("title", "note")
        widgets = {
            "title": forms.TextInput(attrs={"tabindex": "1", "class": "form-control"}),
            "note": forms.Textarea(attrs={"tabindex": "2", "class": "form-control"}),
        }


class FinancialResultsForm(forms.ModelForm):
    """
    決算データ登録用フォーム。
    特定の銘柄の四半期決算の結果（EPS, 売上, ガイダンスの成否など）を入力します。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["recorded_date"].initial = datetime.date.today()

    QUARTER_CHOICES = [
        (1, "1Q"),
        (2, "2Q"),
        (3, "3Q"),
        (4, "4Q"),
    ]

    quarter = forms.ChoiceField(
        choices=QUARTER_CHOICES,
        label="四半期",
        widget=forms.RadioSelect(attrs={"tabindex": "3", "class": "form-check-input"}),
    )

    eps_estimate = forms.FloatField(
        label="EPS予想",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"tabindex": "8", "class": "form-control text-end", "min": "0"}
        ),
    )
    eps_actual = forms.FloatField(
        label="EPS実績",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"tabindex": "9", "class": "form-control text-end", "min": "0"}
        ),
    )
    sales_estimate = forms.FloatField(
        label="売上予想",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"tabindex": "11", "class": "form-control text-end", "min": "0"}
        ),
    )
    sales_actual = forms.FloatField(
        label="売上実績",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"tabindex": "12", "class": "form-control text-end", "min": "0"}
        ),
    )

    y_over_y_growth_rate = forms.FloatField(
        label="前年同期比(%)",
        widget=forms.NumberInput(
            attrs={"tabindex": "13", "class": "form-control text-end"}
        ),
    )

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
            "recorded_date": forms.DateInput(
                attrs={"tabindex": "1", "class": "form-control", "type": "date"}
            ),
            "symbol": forms.Select(attrs={"tabindex": "2", "class": "form-select"}),
            "eps_ok": forms.CheckboxInput(
                attrs={"tabindex": "4", "class": "form-check-input"}
            ),
            "sales_ok": forms.CheckboxInput(
                attrs={"tabindex": "5", "class": "form-check-input"}
            ),
            "guidance_ok": forms.CheckboxInput(
                attrs={"tabindex": "6", "class": "form-check-input"}
            ),
            "eps_unit": forms.Select(attrs={"tabindex": "7", "class": "form-select"}),
            "sales_unit": forms.Select(
                attrs={"tabindex": "10", "class": "form-select"}
            ),
            "note_url": forms.URLInput(
                attrs={"tabindex": "14", "class": "form-control"}
            ),
        }
