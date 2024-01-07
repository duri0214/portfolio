from django import forms
from django.forms import ClearableFileInput

from .models import Company, Land


class CompanyCreateForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ('name', 'image', 'remark', 'category')
        exclude = []
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'remark': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': '圃場名',
            'image': '画像',
            'remark': '備考',
            'category': 'カテゴリー',
        }

    def clean_name(self):
        name = self.cleaned_data['name']
        if 'クサリク' in name:
            raise forms.ValidationError('「クサリク」を含む取引先は登録できなくなりました（取引停止）')

        return name


class LandCreateForm(forms.ModelForm):
    class Meta:
        model = Land
        fields = ('name', 'prefecture', 'location', 'latlon', 'area', 'image', 'remark', 'cultivation_type', 'owner')
        exclude = []
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'prefecture': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: 東京都'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: 港区芝公園４丁目２−８'}),
            'latlon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: 35.658581,139.745433'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: 100'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'remark': forms.TextInput(attrs={'class': 'form-control'}),
            'cultivation_type': forms.Select(attrs={'class': 'form-control'}),
            'owner': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': '圃場名',
            'prefecture': '都道府県',
            'location': '住所',
            'latlon': '緯度・経度',
            'area': '圃場面積（㎡）',
            'image': '画像',
            'remark': '備考',
            'cultivation_type': '栽培タイプ',
            'owner': '所有者',
        }

    def clean_name(self):
        name = self.cleaned_data['name']
        if 'あの圃場' in name:
            raise forms.ValidationError('「あの圃場」を含む圃場名は登録できなくなりました（あいまい）')

        return name


class UploadForm(forms.Form):
    file = forms.FileField(widget=ClearableFileInput(attrs={"class": "form-control"}))
