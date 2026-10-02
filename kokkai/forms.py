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
    """辞書CSVの取り込みか、表記揺れ候補CSVの生成を選ぶフォーム。"""

    def __init__(self, *args, can_generate_candidates=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["generate_candidates"].disabled = not can_generate_candidates

    file = forms.FileField(
        label="CSVファイル",
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )
    generate_candidates = forms.BooleanField(
        label="表記揺れ候補CSVを作る",
        help_text=(
            "チェックすると辞書には登録せず、GPT（OpenAI API）を使用して候補を作ります。"
            "入力行ごとにトークンを消費し、API利用料金が発生する場合があります。"
            "候補を確認してCSVをダウンロードできます。"
        ),
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
