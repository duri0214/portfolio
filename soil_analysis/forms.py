from django import forms
from django.contrib.auth import get_user_model
from django.forms import ClearableFileInput

from .models import (
    Company,
    CompanyCategory,
    Land,
    JmaPrefecture,
    JmaCity,
    LandLedger,
    LandReviewTemplate,
    SamplingMethod,
    UserAttribute,
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
            "name": "企業名",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = CompanyCategory.objects.filter(
            name="農業法人"
        ).order_by("id")


class AnalysisInstitutionForm(forms.ModelForm):
    """分析機関の登録・編集に使うフォーム。"""

    class Meta:
        model = Company
        fields = ("name", "image", "remark")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "remark": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
        labels = {
            "name": "分析機関名",
            "image": "画像",
            "remark": "備考",
        }


class AnalysisInstitutionDeleteForm(forms.Form):
    """台帳参照を引き継いで分析機関を削除するフォーム。"""

    replacement_agency = forms.ModelChoiceField(
        queryset=Company.objects.none(),
        required=False,
        empty_label="選択してください",
        label="引き継ぎ先の分析機関",
    )

    def __init__(self, *args, agency: Company, ledger_count: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.ledger_count = ledger_count
        self.fields["replacement_agency"].queryset = (
            Company.objects.filter(category__name="分析機関")
            .exclude(pk=agency.pk)
            .order_by("name", "id")
        )
        if ledger_count:
            self.fields["replacement_agency"].required = True
            self.fields["replacement_agency"].help_text = (
                f"{ledger_count} 件の既存台帳は、選択した分析機関へ引き継がれます。"
            )

    def clean(self):
        cleaned_data = super().clean()
        if self.ledger_count and not cleaned_data.get("replacement_agency"):
            self.add_error(
                "replacement_agency",
                "台帳を保持するため、引き継ぎ先の分析機関を選択してください。",
            )
        return cleaned_data


class CompanyDeleteForm(forms.Form):
    """圃場も台帳も持たない農業法人の削除確認を受け付けるフォーム。"""

    confirm_deletion = forms.BooleanField(
        label="この農業法人を削除することを確認しました。",
        required=True,
    )


class LandCreateForm(forms.ModelForm):
    jma_prefecture = forms.ModelChoiceField(
        queryset=JmaPrefecture.objects.all(),
        empty_label="選択してください",
        label="都道府県",
        widget=forms.Select(attrs={"class": "form-select", "tabindex": "2"}),
    )
    jma_city = forms.ModelChoiceField(
        queryset=JmaCity.objects.all(),
        empty_label="選択してください",
        label="市区町村",
        widget=forms.Select(attrs={"class": "form-select", "tabindex": "3"}),
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
            "center": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "tabindex": "4",
                    "placeholder": "例: 35.658581,139.745433",
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
                attrs={"class": "form-select", "tabindex": "8"}
            ),
            "owner": forms.Select(attrs={"class": "form-select", "tabindex": "9"}),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        owner_field = self.fields.get("owner")
        if isinstance(owner_field, forms.ModelChoiceField):
            owner_field.queryset = User.objects.filter(
                soil_profile__role=UserAttribute.Role.OWNER
            )

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
        label="計測データ ZIP",
        widget=ClearableFileInput(attrs={"class": "form-control", "tabindex": "1"}),
    )


class SoilMapUploadForm(forms.Form):
    """全国20万分の1土壌図のShape ZIPを受け付けるフォーム。"""

    file = forms.FileField(
        label="全国20万分の1土壌図 ZIP",
        widget=ClearableFileInput(
            attrs={"class": "form-control", "tabindex": "1", "accept": ".zip"}
        ),
        help_text=".shp、.shx、.dbf、.prj を含む全国版ZIPを指定してください。",
    )

    def clean_file(self):
        """ZIP拡張子を確認して、取込サービスへ渡す。"""
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith(".zip"):
            raise forms.ValidationError("ZIPファイルを指定してください。")
        return uploaded_file


class MunicipalityBoundaryUploadForm(forms.Form):
    """国土数値情報の行政区域Shape ZIPを受け付けるフォーム。"""

    file = forms.FileField(
        label="市区町村境界（行政区域データ）ZIP",
        widget=ClearableFileInput(
            attrs={"class": "form-control", "tabindex": "1", "accept": ".zip"}
        ),
        help_text="国土数値情報の全国版（N03）のShape ZIPを指定してください。",
    )

    def clean_file(self):
        """ZIP拡張子を確認して、取込サービスへ渡す。"""
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith(".zip"):
            raise forms.ValidationError("ZIPファイルを指定してください。")
        return uploaded_file


class ChemicalUploadForm(forms.Form):
    file = forms.FileField(
        label="川田研究所 XLSX",
        widget=ClearableFileInput(
            attrs={"class": "form-control", "tabindex": "1", "accept": ".xlsx"}
        ),
    )


class CsvGenerateForm(forms.Form):
    want_to_create_dataset_round = forms.IntegerField(
        label="生成するラウンド数",
        min_value=1,
        max_value=2,
        initial=2,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "1-2の範囲で入力してください",
                "min": "1",
                "max": "2",
            }
        ),
        help_text="連続アップロード検証用に1〜2ラウンド生成できます",
    )
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


class LandReviewForm(forms.Form):
    """台帳の評価コメントを手入力・定型文・GPT下書きから保存するフォーム。"""

    source = forms.ChoiceField(
        label="コメントの作成方法",
        choices=(),
        widget=forms.RadioSelect,
        initial="template",
    )
    template = forms.ModelChoiceField(
        label="定型コメント",
        queryset=LandReviewTemplate.objects.none(),
        required=False,
        empty_label="選択してください",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    comment = forms.CharField(
        label="評価コメント",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": "化学性・物理性・総評を含めて入力してください。",
            }
        ),
    )

    def __init__(self, *args, is_superuser: bool, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            ("template", "定型コメントから選ぶ"),
        ]
        if is_superuser:
            choices.append(("gpt", "GPTで下書きを作成する"))
        choices.append(("manual", "手入力"))
        self.fields["source"].choices = choices
        self.fields["template"].queryset = LandReviewTemplate.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get("source")
        template = cleaned_data.get("template")

        if source == "template":
            if template is None:
                self.add_error("template", "定型コメントを選択してください。")
            else:
                cleaned_data["comment"] = template.comment

        comment = cleaned_data.get("comment", "")
        if not comment.strip():
            self.add_error("comment", "空白だけのコメントは保存できません。")

        return cleaned_data


class LandReviewTemplateForm(forms.ModelForm):
    """定型評価コメントを作成・編集するフォーム。"""

    class Meta:
        model = LandReviewTemplate
        fields = ("name", "comment")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }


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

        self.fields["analytical_agency"].queryset = Company.objects.filter(
            category__name="分析機関"
        ).order_by("name", "id")

        # 必須フィールドのスタイル設定
        for field_name in self.fields:
            field = self.fields[field_name]
            if field.required:
                field.widget.attrs["required"] = True

        sampling_staff_field = self.fields.get("sampling_staff")
        if isinstance(sampling_staff_field, forms.ModelChoiceField):
            sampling_staff_field.queryset = User.objects.filter(
                soil_profile__role=UserAttribute.Role.STAFF
            )

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
