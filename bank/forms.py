from django import forms


class UploadFileForm(forms.Form):
    file = forms.FileField(
        label="ファイル選択",
        help_text="CSVファイル、または複数のCSVファイルをまとめたZIPファイルをアップロードしてください。",
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )
