from django import forms

from shopping.models import Product, UserAttribute


class ProductCreateFormSingle(forms.ModelForm):
    class Meta:
        model = Product
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


class ProductCreateFormBulk(forms.Form):
    """formのname 属性が 'file' になる"""

    file = forms.FileField(
        required=True,
        label="CSVファイル",
        help_text="商品情報が記載されたCSVファイルをアップロードしてください。",
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )

    def clean_file(self):
        """csvファイル要件を満たすかどうかをチェックします"""
        file = self.cleaned_data["file"]
        if not file.name.endswith(".csv"):
            raise forms.ValidationError("拡張子はcsvのみです")
        return file


class ProductEditForm(forms.ModelForm):
    class Meta:
        model = Product
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
    """
    スタッフ作成用フォーム。
    UserAttribute モデルをベースにし、ロールを STAFF に固定して保存します。
    """

    class Meta:
        model = UserAttribute
        fields = ("user", "store", "nickname", "description", "image")
        widgets = {
            "user": forms.Select(attrs={"tabindex": "1", "class": "form-control"}),
            "store": forms.Select(attrs={"tabindex": "2", "class": "form-control"}),
            "nickname": forms.TextInput(
                attrs={"tabindex": "3", "class": "form-control"}
            ),
            "description": forms.Textarea(
                attrs={"tabindex": "4", "class": "form-control", "rows": "5"}
            ),
            "image": forms.ClearableFileInput(attrs={"tabindex": "5"}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.role = UserAttribute.Role.STAFF
        if commit:
            instance.save()
        return instance


class StaffDetailForm(forms.ModelForm):
    """
    スタッフ詳細表示用フォーム。
    すべてのフィールドを読み取り専用にします。
    """

    class Meta:
        model = UserAttribute
        fields = ("user", "store", "nickname", "description")
        widgets = {
            "user": forms.Select(
                attrs={"readonly": "readonly", "class": "form-control-plaintext"}
            ),
            "store": forms.Select(
                attrs={"readonly": "readonly", "class": "form-control-plaintext"}
            ),
            "nickname": forms.TextInput(
                attrs={"readonly": "readonly", "class": "form-control-plaintext"}
            ),
            "description": forms.Textarea(
                attrs={
                    "readonly": "readonly",
                    "class": "form-control-plaintext",
                    "rows": "5",
                }
            ),
        }


class StaffEditForm(forms.ModelForm):
    """
    スタッフ編集用フォーム。
    """

    class Meta:
        model = UserAttribute
        fields = ("store", "nickname", "description", "image")
        widgets = {
            "store": forms.Select(attrs={"tabindex": "1", "class": "form-control"}),
            "nickname": forms.TextInput(
                attrs={"tabindex": "2", "class": "form-control"}
            ),
            "description": forms.Textarea(
                attrs={"tabindex": "3", "class": "form-control", "rows": "5"}
            ),
            "image": forms.ClearableFileInput(attrs={"tabindex": "4"}),
        }


class PurchaseForm(forms.Form):
    """商品購入のためのフォーム"""

    quantity = forms.IntegerField(
        label="数量",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "購入数量を入力"}
        ),
    )
