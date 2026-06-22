from django import forms
from .models import Bank


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = Bank
        fields = ["name", "financial_code", "branch_code", "account_number", "remark"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "financial_code": forms.TextInput(
                attrs={"class": "form-control", "inputmode": "numeric"}
            ),
            "branch_code": forms.TextInput(
                attrs={"class": "form-control", "inputmode": "numeric"}
            ),
            "account_number": forms.TextInput(
                attrs={"class": "form-control", "inputmode": "numeric"}
            ),
            "remark": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
        labels = {
            "name": "口座名",
            "financial_code": "金融機関コード",
            "branch_code": "店番",
            "account_number": "口座番号",
            "remark": "備考",
        }
        help_texts = {
            "name": "画面上で区別しやすい名前を入力してください。",
            "financial_code": "MUFGは 0005 です。",
            "branch_code": "3桁で入力してください。",
            "account_number": "7桁で入力してください。",
        }

    def clean_financial_code(self):
        financial_code = self.cleaned_data["financial_code"]
        if not financial_code.isdigit():
            raise forms.ValidationError("金融機関コードは数字で入力してください。")
        return financial_code

    def clean_branch_code(self):
        branch_code = self.cleaned_data["branch_code"]
        if not branch_code:
            return branch_code
        if not branch_code.isdigit() or len(branch_code) != 3:
            raise forms.ValidationError("店番は3桁の数字で入力してください。")
        return branch_code

    def clean_account_number(self):
        account_number = self.cleaned_data["account_number"]
        if not account_number:
            return account_number
        if not account_number.isdigit() or len(account_number) != 7:
            raise forms.ValidationError("口座番号は7桁の数字で入力してください。")
        return account_number


class UploadFileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bank"].queryset = Bank.objects.order_by("name")

    bank = forms.ModelChoiceField(
        queryset=Bank.objects.none(),
        label="対象口座",
        empty_label="口座を選択してください",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    file = forms.FileField(
        label="ファイル選択",
        help_text="CSVファイル、または複数のCSVファイルをまとめたZIPファイルをアップロードしてください。",
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )
