from django import forms

from .models import Item, Invoice


class RegisterForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ('warehouse', 'serial_number', 'name', 'price', 'pos_x', 'pos_y', 'pos_z', 'staff')


class InvoiceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rental_start_date'].widget.attrs['class'] = 'datepicker'
        self.fields['rental_end_date'].widget.attrs['class'] = 'datepicker'

    class Meta:
        model = Invoice
        fields = ('company', 'billing_person', 'rental_start_date', 'rental_end_date', 'staff')
