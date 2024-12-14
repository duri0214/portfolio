from django import forms


class UserTextForm(forms.Form):
    question = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        for field in self.base_fields.values():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["rows"] = 3
        super().__init__(*args, **kwargs)
