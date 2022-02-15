"""forms.py"""
from django import forms
from .models import Products, Staff


class RegisterFormSingle(forms.ModelForm):
    """ SingleRegistrationForm """
    class Meta:
        """Meta"""
        model = Products
        fields = ('code', 'name', 'price', 'picture', 'description')


class RegisterFormBulk(forms.Form):
    """ formのname 属性が 'file' になる """
    file = forms.FileField(required=True, label='')

    def clean_file(self):
        """csvファイル要件を満たすかどうかをチェックします"""
        file = self.cleaned_data['file']
        if not file.name.endswith('.csv'):
            raise forms.ValidationError('拡張子はcsvのみです')
        return file


class ProductEditForm(forms.ModelForm):
    """ ProductEditForm """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].widget.attrs['readonly'] = 'readonly'
        self.fields['code'].widget.attrs['width'] = '10%'
        self.fields['name'].widget.attrs['width'] = '15%'
        self.fields['price'].widget.attrs['width'] = '10%'
        self.fields['description'].widget.attrs['width'] = '40%'

    class Meta:
        """Meta"""
        model = Products
        fields = ('code', 'name', 'price', 'description')
