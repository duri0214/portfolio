from django import forms


class ReadingSupportCsvImportForm(forms.Form):
    """読み仮名支援辞書CSVの管理画面取り込みフォーム。"""

    file = forms.FileField(label="CSVファイル")
    update_existing = forms.BooleanField(
        label="既存データを更新する",
        required=False,
        help_text="同じ正規化表記の既存データをCSVの内容で更新します。",
    )


class ReadingSupportDraftGenerationForm(forms.Form):
    """Web本文から辞書候補下書きを作るフォーム。"""

    source_url = forms.URLField(
        label="WebページURL",
        required=False,
        help_text="指定するとページ本文を取得してGPTへ渡します。",
    )
    source_text = forms.CharField(
        label="貼り付け本文",
        required=False,
        widget=forms.Textarea(attrs={"rows": 14}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("source_url") and not cleaned_data.get("source_text"):
            raise forms.ValidationError(
                "WebページURLまたは貼り付け本文を指定してください。"
            )
        return cleaned_data
