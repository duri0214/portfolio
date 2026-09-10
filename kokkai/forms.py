from django import forms

from .models import ReadingSupportEntry


class ReadingSupportEntryForm(forms.ModelForm):
    """読み仮名支援辞書のエントリーを登録・編集するフォーム。"""

    class Meta:
        model = ReadingSupportEntry
        fields = (
            "surface",
            "reading",
            "description",
            "source_url",
        )
        widgets = {
            "surface": forms.TextInput(attrs={"class": "form-control"}),
            "reading": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "source_url": forms.URLInput(attrs={"class": "form-control"}),
        }


class ReadingSupportCsvImportForm(forms.Form):
    """読み仮名支援辞書のCSVを取り込むフォーム。"""

    file = forms.FileField(
        label="CSVファイル",
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )
    update_existing = forms.BooleanField(
        label="既存データを更新する",
        required=False,
        help_text="同じ正規化表記の既存データをCSVの内容で更新します。",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
