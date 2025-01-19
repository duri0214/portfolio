from django import forms


class CoordinateForm(forms.Form):
    latitude = forms.FloatField(
        label="緯度 (Latitude)",
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "例: 35.6895"}
        ),
    )
    longitude = forms.FloatField(
        label="経度 (Longitude)",
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "例: 139.6917"}
        ),
    )
