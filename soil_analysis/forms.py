from django import forms
from django.forms import ClearableFileInput

from .models import Company, Land, JmaPrefecture, JmaCity


class CompanyCreateForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ("name", "image", "remark", "category")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "tabindex": "1"}),
            "image": forms.ClearableFileInput(
                attrs={"class": "form-control", "tabindex": "2"}
            ),
            "remark": forms.TextInput(attrs={"class": "form-control", "tabindex": "3"}),
            "category": forms.Select(attrs={"class": "form-control", "tabindex": "4"}),
        }
        labels = {
            "name": "圃場名",
            "image": "画像",
            "remark": "備考",
            "category": "カテゴリー",
        }

    def clean_name(self):
        name = self.cleaned_data["name"]
        if "クサリク" in name:
            raise forms.ValidationError(
                "「クサリク」を含む取引先は登録できなくなりました（取引停止）"
            )

        return name


class LandCreateForm(forms.ModelForm):
    jma_prefecture = forms.ModelChoiceField(
        queryset=JmaPrefecture.objects.all(), empty_label="選択してください"
    )
    jma_city = forms.ModelChoiceField(
        queryset=JmaCity.objects.all(), empty_label="選択してください"
    )

    class Meta:
        model = Land
        fields = (
            "name",
            "latlon",
            "jma_prefecture",
            "jma_city",
            "area",
            "image",
            "remark",
            "cultivation_type",
            "owner",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "tabindex": "1"}),
            "latlon": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "tabindex": "2",
                    "placeholder": "例: 35.658581,139.745433",
                }
            ),
            # TODO: なぜか bootstrap が反映されない（react化で解決したほうがよさそう）
            "jma_prefecture": forms.Select(
                attrs={
                    "class": "form-control",
                    "tabindex": "3",
                    "placeholder": "例: 兵庫県",
                }
            ),
            # TODO: なぜか bootstrap が反映されない（react化で解決したほうがよさそう）
            "jma_city": forms.Select(
                attrs={
                    "class": "form-control",
                    "tabindex": "4",
                    "placeholder": "例: 姫路市",
                }
            ),
            "area": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "tabindex": "5",
                    "placeholder": "例: 100",
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={"class": "form-control", "tabindex": "6"}
            ),
            "remark": forms.TextInput(attrs={"class": "form-control", "tabindex": "7"}),
            "cultivation_type": forms.Select(
                attrs={"class": "form-control", "tabindex": "8"}
            ),
            "owner": forms.Select(attrs={"class": "form-control", "tabindex": "9"}),
            "company": forms.HiddenInput(),
        }
        labels = {
            "name": "圃場名*",
            "latlon": "緯度・経度*",
            "jma_prefecture": "都道府県*",
            "jma_city": "市区町村*",
            "area": "圃場面積（㎡）",
            "image": "画像",
            "remark": "備考",
            "cultivation_type": "栽培タイプ*",
            "owner": "所有者*",
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        company_id = self.data.get("company-id")
        if "あの" in name:
            raise forms.ValidationError(
                "「あの」を含む圃場名は登録できなくなりました（あいまい）"
            )

        if Land.objects.filter(name=name, company_id=company_id).exists():
            raise forms.ValidationError(
                "この名前の圃場は既に存在します。別の名前を選択してください"
            )

        return name


class UploadForm(forms.Form):
    file = forms.FileField(
        widget=ClearableFileInput(attrs={"class": "form-control", "tabindex": "1"})
    )
