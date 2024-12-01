from django import forms

from shopping.models import Products, Staff


class RegisterFormSingle(forms.ModelForm):
    class Meta:
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
    class Meta:
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


class StaffCreateForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ("name", "description", "image", "store", "user")
        widgets = {
            "name": forms.TextInput(attrs={"tabindex": "1", "class": "form-control"}),
            "description": forms.Textarea(
                attrs={"tabindex": "2", "class": "form-control", "rows": "5"}
            ),
            "image": forms.ClearableFileInput(attrs={"tabindex": "3"}),
            "store": forms.Select(attrs={"tabindex": "4", "class": "form-control"}),
            "user": forms.Select(attrs={"tabindex": "5", "class": "form-control"}),
        }


class StaffEditForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ("name", "description", "image", "store")
        widgets = {
            "name": forms.TextInput(attrs={"tabindex": "1", "class": "form-control"}),
            "description": forms.Textarea(
                attrs={"tabindex": "2", "class": "form-control", "rows": "5"}
            ),
            "image": forms.ClearableFileInput(attrs={"tabindex": "3"}),
            "store": forms.Select(attrs={"tabindex": "4", "class": "form-control"}),
        }


class StaffDetailForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ("name", "description", "image", "store")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "readonly": "readonly",
                    "class": "form-control-plaintext",
                    "id": "staticName",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "readonly": "readonly",
                    "class": "form-control-plaintext",
                    "id": "staticDescription",
                    "rows": "5",
                }
            ),
            "image": forms.ClearableFileInput(attrs={"readonly": "readonly"}),
            "store": forms.Select(
                attrs={
                    "readonly": "readonly",
                    "class": "form-control-plaintext",
                    "id": "staticStore",
                }
            ),
        }
