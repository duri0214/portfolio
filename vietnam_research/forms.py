from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Articles, Watchlist


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
        self.user = kwargs.pop("user", None)
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

    def clean(self):
        cleaned_data = super().clean()
        symbol = cleaned_data.get("symbol")
        user = getattr(self, "user", None)

        if symbol and user:
            # 新規登録（instance.pkがない）の場合に重複チェック
            if not self.instance.pk:
                if Watchlist.objects.filter(user=user, symbol=symbol).exists():
                    self.add_error(
                        "symbol", "この銘柄はすでにウォッチリストに登録されています。"
                    )
        return cleaned_data


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
