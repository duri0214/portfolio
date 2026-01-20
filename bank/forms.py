from django import forms
from .models import Bank


class UploadFileForm(forms.Form):
    bank = forms.ModelChoiceField(
        queryset=Bank.objects.all(),
        label="対象口座",
        empty_label="口座を選択してください",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    file = forms.FileField(
        label="ファイル選択",
        help_text="CSVファイル、または複数のCSVファイルをまとめたZIPファイルをアップロードしてください。",
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )
