from django import forms

from llm_chat.domain.valueobject.completion.riddle import GenderType
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class UserTextForm(forms.Form):
    question = forms.CharField(widget=forms.Textarea)

    USE_CASE_TYPE_CHOICES = [
        (UseCaseType.OPENAI_GPT_STREAMING, "OpenAI GPT Streaming"),
        (UseCaseType.OPENAI_IMAGE, "OpenAI Image Generation"),
        (UseCaseType.OPENAI_TEXT_TO_SPEECH, "OpenAI Text to Speech"),
        (UseCaseType.OPENAI_SPEECH_TO_TEXT, "OpenAI Speech to Text"),
        (UseCaseType.OPENAI_RAG, "OpenAI RAG"),
        (UseCaseType.RIDDLE, "Riddle"),
    ]

    use_case_type = forms.ChoiceField(
        choices=USE_CASE_TYPE_CHOICES,
        label="Use Case Type",
        initial=UseCaseType.OPENAI_GPT_STREAMING,  # デフォルト値
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    audio_file = forms.FileField(
        label="Upload Audio File",
        required=False,  # `OpenAISpeechToText` のみで必要
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": "audio/*"}
        ),
    )

    GENDER_CHOICES = [
        (GenderType.MAN.value, "男性"),
        (GenderType.WOMAN.value, "女性"),
    ]

    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        label="Gender",
        initial=GenderType.MAN.value,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        rag_pdf_choices = kwargs.pop("rag_pdf_choices", [])
        for field in self.base_fields.values():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["rows"] = 3
        super().__init__(*args, **kwargs)
        self.fields["rag_pdf"].choices = [
            ("", "PDFを選択してください"),
            *rag_pdf_choices,
        ]

    rag_pdf = forms.ChoiceField(
        choices=[],
        label="RAG PDF",
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class RiddleCSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="CSVファイル",
        help_text="フォーマット: order,question_text,answer_text",
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".csv"}
        ),
    )


class MultiplePdfFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiplePdfFileField(forms.FileField):
    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        cleaned_files = [forms.FileField.clean(self, file, initial) for file in files]
        for file in cleaned_files:
            if not file.name.lower().endswith(".pdf"):
                raise forms.ValidationError("PDFファイルを選択してください。")
        return cleaned_files


class OpenAIRagPdfUploadForm(forms.Form):
    files = MultiplePdfFileField(
        label="PDFファイル",
        widget=MultiplePdfFileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf,application/pdf",
                "multiple": True,
            }
        ),
    )
