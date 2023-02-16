from django import forms

from .models import Item, Invoice


class ItemCreateForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ('warehouse', 'serial_number', 'name', 'price', 'pos_x', 'pos_y', 'pos_z', 'staff')


class InvoiceCreateForm(forms.ModelForm):
    # TODO: 会社名を選んだら、会社名の請求担当者しか選べない形にしたい
    #  https://blog.narito.ninja/detail/50
    # billing_person = ModelChoiceField(label="請求側担当者", queryset=BillingPerson.objects.filter(company=99))

    class Meta:
        model = Invoice
        fields = ('company', 'billing_person', 'rental_start_date', 'rental_end_date', 'staff')
