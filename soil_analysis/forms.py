from django import forms
from django.contrib.auth import get_user_model
from django.forms import ClearableFileInput

from .models import (
    Company,
    Land,
    JmaPrefecture,
    JmaCity,
    LandLedger,
    SamplingMethod,
)

User = get_user_model()


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
            "category": forms.Select(attrs={"class": "form-select", "tabindex": "4"}),
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
        queryset=JmaPrefecture.objects.all(),
        empty_label="選択してください",
        label="都道府県",
    )
    jma_city = forms.ModelChoiceField(
        queryset=JmaCity.objects.all(), empty_label="選択してください", label="市区町村"
    )

    class Meta:
        model = Land
        fields = (
            "name",
            "jma_prefecture",
            "jma_city",
            "center",
            "area",
            "image",
            "remark",
            "cultivation_type",
            "owner",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "tabindex": "1"}),
            "jma_prefecture": forms.Select(
                attrs={
                    "class": "form-select",
                    "tabindex": "2",
                    "placeholder": "都道府県を選択してください",
                }
            ),
            "jma_city": forms.Select(
                attrs={
                    "class": "form-select",
                    "tabindex": "3",
                    "placeholder": "市区町村を選択してください",
                }
            ),
            "center": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "tabindex": "4",
                    "placeholder": "例: 35.658581,139.745433",
                    "value": "35.658581,139.745433",
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
            "name": "圃場名",
            "jma_prefecture": "都道府県",
            "jma_city": "市区町村",
            "center": "中心座標",
            "area": "圃場面積（㎡）",
            "image": "画像",
            "remark": "備考",
            "cultivation_type": "栽培タイプ",
            "owner": "所有者",
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


class CsvGenerateForm(forms.Form):
    num_fields = forms.IntegerField(
        label="生成する圃場数",
        min_value=1,
        max_value=16,
        initial=3,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "1-16の範囲で入力してください",
                "min": "1",
                "max": "16",
            }
        ),
        help_text="1〜16圃場まで指定可能です（計測器の制約により最大16圃場）",
    )


class LandLedgerCreateForm(forms.ModelForm):
    """
    帳簿（LandLedger）の新規作成フォーム
    Field Group画面から直接新規帳簿を作成する際に使用
    """

    class Meta:
        model = LandLedger
        fields = [
            "sampling_date",
            "land",
            "crop",
            "land_period",
            "sampling_method",
            "analytical_agency",
            "sampling_staff",
        ]
        widgets = {
            "sampling_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date", "tabindex": "1"}
            ),
            "land": forms.Select(attrs={"class": "form-select", "tabindex": "2"}),
            "crop": forms.Select(attrs={"class": "form-select", "tabindex": "3"}),
            "land_period": forms.Select(
                attrs={"class": "form-select", "tabindex": "4"}
            ),
            "sampling_method": forms.Select(
                attrs={"class": "form-select", "tabindex": "5"}
            ),
            "analytical_agency": forms.Select(
                attrs={"class": "form-select", "tabindex": "6"}
            ),
            "sampling_staff": forms.Select(
                attrs={"class": "form-select", "tabindex": "7"}
            ),
        }
        labels = {
            "sampling_date": "採土日*",
            "land": "圃場*",
            "crop": "作物*",
            "land_period": "時期*",
            "sampling_method": "採土法*",
            "analytical_agency": "分析機関*",
            "sampling_staff": "採土者*",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 必須フィールドのスタイル設定
        for field_name in self.fields:
            field = self.fields[field_name]
            if field.required:
                field.widget.attrs["required"] = True

        # デフォルトで5点法を選択状態にする
        try:
            default_sampling_method = SamplingMethod.objects.filter(
                name__icontains="5点法"
            ).first()
            if default_sampling_method:
                self.fields["sampling_method"].initial = default_sampling_method.id
        except SamplingMethod.DoesNotExist:
            pass

    def clean(self):
        cleaned_data = super().clean()
        land = cleaned_data.get("land")
        land_period = cleaned_data.get("land_period")

        # 同一圃場・同一時期の帳簿が既に存在するかチェック
        if land and land_period:
            existing_ledger = LandLedger.objects.filter(
                land=land, land_period=land_period
            ).first()

            if existing_ledger:
                raise forms.ValidationError(
                    f"圃場「{land.name}」の{land_period.year}年{land_period.name}の帳簿は既に存在します。"
                )

        return cleaned_data
