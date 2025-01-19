from django import forms


class UserTextForm(forms.Form):
    question = forms.CharField(widget=forms.Textarea)

    USE_CASE_CHOICES = [
        ("OpenAIGpt", "OpenAI GPT"),
        ("Gemini", "Gemini"),
        ("OpenAIDalle", "OpenAI Dall-e"),
        ("OpenAITextToSpeech", "OpenAI Text to Speech"),
        ("OpenAISpeechToText", "OpenAI Speech to Text"),
        ("OpenAIRag", "OpenAI RAG"),
    ]

    use_case_type = forms.ChoiceField(
        choices=USE_CASE_CHOICES,
        label="Use Case Type",
        initial="OpenAIGpt",  # デフォルト値
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    audio_file = forms.FileField(
        label="Upload Audio File",
        required=False,  # `OpenAISpeechToText` のみで必要
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": "audio/*"}
        ),
    )

    def __init__(self, *args, **kwargs):
        for field in self.base_fields.values():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["rows"] = 3
        super().__init__(*args, **kwargs)
