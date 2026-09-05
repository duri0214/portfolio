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
            "entry_type": forms.Select(attrs={"class": "form-select"}),
            "surface": forms.TextInput(attrs={"class": "form-control"}),
            "reading": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "category": forms.TextInput(attrs={"class": "form-control"}),
            "source_url": forms.URLInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
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
            "entry_type": forms.Select(attrs={"class": "form-select"}),
            "surface": forms.TextInput(attrs={"class": "form-control"}),
            "reading": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "category": forms.TextInput(attrs={"class": "form-control"}),
            "source_url": forms.URLInput(attrs={"class": "form-control"}),
            "needs_review": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_approved": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "review_note": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class ReadingSupportCsvImportForm(forms.Form):
    """KOKKAI内で読み仮名支援辞書CSVを取り込むフォーム。"""

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


class ReadingSupportDraftGenerationForm(forms.Form):
    """Web本文から辞書候補を作るフォーム。"""

    source_url = forms.URLField(
        label="WebページURL",
        required=False,
        help_text="指定するとページ本文を取得してGPTへ渡します。",
        widget=forms.URLInput(attrs={"class": "form-control"}),
    )
    source_text = forms.CharField(
        label="貼り付け本文",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 14}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("source_url") and not cleaned_data.get("source_text"):
            raise forms.ValidationError(
                "WebページURLまたは貼り付け本文を指定してください。"
            )
        return cleaned_data
