import calendar
from datetime import date

from django import forms
from django.utils import timezone

from .models import Facility, FacilityAvailability


class FacilityAvailabilityForm(forms.ModelForm):
    """福祉事務所の空き状況入力フォーム"""

    # 月次データ入力用のフィールド（YYYY-MM形式）
    year_month = forms.CharField(
        label="年月",
        max_length=7,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "YYYY-MM形式で入力",
                "pattern": "\\d{4}-\\d{2}",
                "title": "YYYY-MM形式で入力してください（例：2025-08）",
            }
        ),
        initial=timezone.now().strftime("%Y-%m"),
        help_text="バックデート入力する場合は変更してください（例：2025-07）。入力された年月は月末日として処理されます。",
    )

    facility = forms.ModelChoiceField(
        label="福祉事務所",
        queryset=Facility.objects.all().order_by("name"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = FacilityAvailability
        fields = ["facility", "available_count", "remarks"]
        widgets = {
            "available_count": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "空き人数を入力",
                }
            ),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "備考があれば入力してください",
                }
            ),
        }

    def clean_available_count(self):
        """空き人数のバリデーション"""
        available_count = self.cleaned_data.get("available_count")
        if available_count is not None and available_count < 0:
            raise forms.ValidationError("空き人数は0以上の値を入力してください")
        return available_count

    def clean_year_month(self):
        """年月のバリデーション"""
        year_month = self.cleaned_data.get("year_month")
        try:
            # YYYY-MM形式かチェック
            year, month = year_month.split("-")
            if not (len(year) == 4 and len(month) == 2):
                raise forms.ValidationError(
                    "YYYY-MM形式で入力してください（例：2025-08）"
                )
            # 数値変換可能かチェック
            year = int(year)
            month = int(month)
            # 月の範囲チェック
            if not (1 <= month <= 12):
                raise forms.ValidationError("月は1～12の範囲で入力してください")
        except ValueError:
            raise forms.ValidationError("YYYY-MM形式で入力してください（例：2025-08）")
        return year_month

    def save(self, commit=True):
        """空き状況を保存
        空き人数に応じて状態を設定:
        - 0: 'unavailable' (空きなし)
        - 1-3: 'limited' (残りわずか)
        - 4以上: 'available' (空きあり)

        また、入力された年月をtarget_dateフィールドに変換して保存
        """
        instance = super().save(commit=False)

        # 空き人数に応じて状態を設定
        available_count = self.cleaned_data.get("available_count", 0)
        if available_count == 0:
            instance.status = "unavailable"  # 空きなし
        elif 1 <= available_count <= 3:
            instance.status = "limited"  # 残りわずか
        else:  # 4以上
            instance.status = "available"  # 空きあり

        # YYYY-MM形式から対象年月のDateFieldを設定
        year_month = self.cleaned_data.get("year_month")
        if year_month:
            year, month = year_month.split("-")
            # 月末日を対象日として設定
            year = int(year)
            month = int(month)
            last_day = calendar.monthrange(year, month)[1]
            instance.target_date = date(year, month, last_day)

        if commit:
            instance.save()
        return instance
