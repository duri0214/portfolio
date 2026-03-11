from django import forms

from llm_chat.domain.valueobject.completion.riddle import GenderType
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class UserTextForm(forms.Form):
    question = forms.CharField(widget=forms.Textarea)

    USE_CASE_TYPE_CHOICES = [
        (UseCaseType.OPENAI_GPT, "OpenAI GPT"),
        (UseCaseType.OPENAI_GPT_STREAMING, "OpenAI GPT Streaming"),
        (UseCaseType.GEMINI, "Gemini"),
        (UseCaseType.OPENAI_DALLE, "OpenAI Dall-e"),
        (UseCaseType.OPENAI_TEXT_TO_SPEECH, "OpenAI Text to Speech"),
        (UseCaseType.OPENAI_SPEECH_TO_TEXT, "OpenAI Speech to Text"),
        (UseCaseType.OPENAI_RAG, "OpenAI RAG"),
        (UseCaseType.RIDDLE, "Riddle"),
    ]

    use_case_type = forms.ChoiceField(
        choices=USE_CASE_TYPE_CHOICES,
        label="Use Case Type",
        initial=UseCaseType.OPENAI_GPT,  # デフォルト値
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
        for field in self.base_fields.values():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["rows"] = 3
        super().__init__(*args, **kwargs)
