from django import forms

from .models import ReadingSupportEntry


class ReadingSupportEntryForm(forms.ModelForm):
    """既存の読み仮名支援辞書エントリーを編集するフォーム。"""

    class Meta:
        model = ReadingSupportEntry
        fields = (
            "word",
            "reading",
            "description",
            "source_url",
        )
        widgets = {
            "word": forms.TextInput(attrs={"class": "form-control"}),
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
