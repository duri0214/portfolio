from django import forms

from lib.geo.valueobject.coord import GoogleMapsCoord
from shopping.domain.valueobject.store_planning import AREA_HIERARCHY_LEVEL_BLOCK
from shopping.models import Product, StorePlanningTargetStore, UserAttribute


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


class StorePlanningTargetStoreCreateForm(forms.ModelForm):
    """出店計画で選択するサンプル店舗候補の登録フォーム。"""

    google_maps_coord = forms.CharField(
        label="Googleマップ座標",
        required=True,
        help_text=(
            "Googleマップでピンを右クリックしてコピーした座標を貼り付けます。"
            "カンマの左側を緯度、右側を経度として保存します。"
        ),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "35.681236, 139.767125",
            }
        ),
    )
    prefecture_name = forms.CharField(
        label="E-Stat都道府県名",
        help_text="e-Stat CSVの「都道府県名」です。例: 東京都",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "東京都"}
        ),
    )
    city_name = forms.CharField(
        label="E-Stat市区町村名",
        help_text="e-Stat CSVの「市区町村名」です。例: 渋谷区",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "渋谷区"}
        ),
    )

    class Meta:
        model = StorePlanningTargetStore
        fields = (
            "slug",
            "name",
            "address",
            "google_maps_coord",
            "city_code",
            "town_code",
            "business_type_label",
            "business_search_query",
            "prefecture_name",
            "city_name",
            "large_area_name",
            "small_area_name",
            "is_active",
        )
        widgets = {
            "slug": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "test-taproom"}
            ),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Test Taproom"}
            ),
            "address": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "東京都渋谷区代々木"}
            ),
            "city_code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "13113"}
            ),
            "town_code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "030002"}
            ),
            "business_type_label": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "カフェ"}
            ),
            "business_search_query": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "カフェ"}
            ),
            "large_area_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "代々木"}
            ),
            "small_area_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "二丁目"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "city_code": "E-Stat市区町村コード",
            "town_code": "E-Stat町丁字コード",
            "business_type_label": "業態",
            "business_search_query": "Google Maps同業検索語",
            "large_area_name": "E-Stat大字・町名",
            "small_area_name": "E-Stat字・丁目名",
        }
        help_texts = {
            "slug": "URLの ?store= に入る半角英数字・ハイフンの識別子です。例: test-taproom",
            "name": "画面の店舗選択や見出しに表示する名前です。",
            "address": "Googleマップ検索や候補地の説明に使う住所です。",
            "city_code": "e-Stat CSVの「市区町村コード」です。例: 渋谷区は13113",
            "town_code": "e-Stat CSVの「町丁字コード」です。例: 代々木二丁目は030002",
            "business_type_label": "出店計画画面で表示する業態名です。例: カフェ",
            "business_search_query": "周辺同業店舗の検索に使う語です。例: カフェ、クラフトビール",
            "large_area_name": "e-Stat CSVの「大字・町名」です。例: 代々木",
            "small_area_name": "e-Stat CSVの「字・丁目名」です。例: 二丁目",
            "is_active": "オンにすると出店計画画面の店舗選択に表示します。",
        }

    def clean(self):
        cleaned_data = super().clean()
        google_maps_coord = cleaned_data.get("google_maps_coord", "").strip()
        if not google_maps_coord:
            return cleaned_data

        coord_parts = [part.strip() for part in google_maps_coord.split(",")]
        if len(coord_parts) != 2:
            self.add_error(
                "google_maps_coord",
                "Googleマップ座標は「緯度, 経度」の形式で入力してください。",
            )
            return cleaned_data

        try:
            latitude = float(coord_parts[0])
            longitude = float(coord_parts[1])
        except ValueError:
            self.add_error(
                "google_maps_coord",
                "Googleマップ座標は数値2つをカンマ区切りで入力してください。",
            )
            return cleaned_data

        if not -90 <= latitude <= 90:
            self.add_error(
                "google_maps_coord",
                "カンマの左側は緯度です。Googleマップの座標を「緯度, 経度」の順で貼り付けてください。",
            )
            return cleaned_data
        if not -180 <= longitude <= 180:
            self.add_error(
                "google_maps_coord",
                "カンマの右側は経度です。Googleマップの座標を「緯度, 経度」の順で貼り付けてください。",
            )
            return cleaned_data

        cleaned_data["google_maps_coord"] = GoogleMapsCoord(
            latitude=latitude,
            longitude=longitude,
        )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        google_maps_coord = self.cleaned_data["google_maps_coord"]
        instance.latitude = google_maps_coord.latitude
        instance.longitude = google_maps_coord.longitude
        instance.population_area = self._population_area()
        instance.area_hierarchy_level = AREA_HIERARCHY_LEVEL_BLOCK
        if commit:
            instance.save()
        return instance

    def _population_area(self) -> str:
        return "".join(
            [
                self.cleaned_data["prefecture_name"],
                self.cleaned_data["city_name"],
                self.cleaned_data.get("large_area_name", ""),
                self.cleaned_data.get("small_area_name", ""),
            ]
        )


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
