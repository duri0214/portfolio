from django import forms

from .models import ReadingSupportDraftCandidate, ReadingSupportEntry


class ReadingSupportEntryForm(forms.ModelForm):
    """KOKKAI内の読み仮名支援辞書エントリを登録・編集するフォーム。"""

    class Meta:
        model = ReadingSupportEntry
        fields = (
            "entry_type",
            "surface",
            "reading",
            "description",
            "category",
            "source_url",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class ReadingSupportDraftCandidateForm(forms.ModelForm):
    """KOKKAI内でGPT候補を確認・修正し、登録承認するフォーム。"""

    class Meta:
        model = ReadingSupportDraftCandidate
        fields = (
            "entry_type",
            "surface",
            "reading",
            "description",
            "category",
            "source_url",
            "needs_review",
            "is_approved",
            "review_note",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "review_note": forms.Textarea(attrs={"rows": 2}),
        }


class ReadingSupportCsvImportForm(forms.Form):
    """KOKKAI内で読み仮名支援辞書CSVを取り込むフォーム。"""

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
