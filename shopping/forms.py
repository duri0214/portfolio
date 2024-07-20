"""forms.py"""

from django import forms

from .models import Products


class RegisterFormSingle(forms.ModelForm):
    """SingleRegistrationForm"""

    class Meta:
        """Meta"""

        model = Products
        fields = ("code", "name", "price", "picture", "description")


class RegisterFormBulk(forms.Form):
    """formのname 属性が 'file' になる"""

    file = forms.FileField(required=True, label="")

    def clean_file(self):
        """csvファイル要件を満たすかどうかをチェックします"""
        file = self.cleaned_data["file"]
        if not file.name.endswith(".csv"):
            raise forms.ValidationError("拡張子はcsvのみです")
        return file
