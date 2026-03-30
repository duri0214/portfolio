import datetime

from django import forms

from .models import FinancialResultWatch


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
            "ticker",
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
            "ticker": forms.TextInput(attrs={"tabindex": "2", "class": "form-control"}),
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
