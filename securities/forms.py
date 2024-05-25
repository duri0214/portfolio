from django import forms
from django.forms import ClearableFileInput


class UploadForm(forms.Form):
    file = forms.FileField(widget=ClearableFileInput(attrs={"class": "form-control"}))
