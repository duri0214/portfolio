"""forms.py"""

from django import forms

from .models import Products


class RegisterFormSingle(forms.ModelForm):
    """SingleRegistrationForm"""

    class Meta:
        """Meta"""

        model = Products
        fields = ("code", "name", "price", "picture", "description")
        widgets = {
            "code": forms.TextInput(attrs={"tabindex": "1", "class": "form-control"}),
            "name": forms.TextInput(attrs={"tabindex": "2", "class": "form-control"}),
            "price": forms.NumberInput(
                attrs={"tabindex": "3", "class": "form-control"}
            ),
            "picture": forms.FileInput(
                attrs={"tabindex": "4", "class": "form-control"}
            ),
            "description": forms.TextInput(
                attrs={"tabindex": "5", "class": "form-control"}
            ),
        }


class RegisterFormBulk(forms.Form):
    """formのname 属性が 'file' になる"""

    file = forms.FileField(required=True, label="")

    def clean_file(self):
        """csvファイル要件を満たすかどうかをチェックします"""
        file = self.cleaned_data["file"]
        if not file.name.endswith(".csv"):
            raise forms.ValidationError("拡張子はcsvのみです")
        return file


class ProductEditForm(forms.ModelForm):
    """ProductEditForm"""

    class Meta:
        """Meta"""

        model = Products
        fields = ("code", "name", "price", "description")
        widgets = {
            "code": forms.TextInput(attrs={"tabindex": "1", "class": "form-control"}),
            "name": forms.TextInput(attrs={"tabindex": "2", "class": "form-control"}),
            "price": forms.NumberInput(
                attrs={"tabindex": "3", "class": "form-control"}
            ),
            "description": forms.Textarea(
                attrs={"tabindex": "4", "class": "form-control", "rows": "5"}
            ),
        }
