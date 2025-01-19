from django import forms

from .models import Item, Invoice


class ItemCreateForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = (
            "warehouse",
            "serial_number",
            "name",
            "price",
            "pos_x",
            "pos_y",
            "pos_z",
            "staff",
        )
        widgets = {
            "warehouse": forms.Select(attrs={"tabindex": "1", "class": "form-control"}),
            "serial_number": forms.TextInput(
                attrs={"tabindex": "2", "class": "form-control"}
            ),
            "name": forms.TextInput(attrs={"tabindex": "3", "class": "form-control"}),
            "price": forms.NumberInput(
                attrs={"tabindex": "4", "class": "form-control"}
            ),
            "pos_x": forms.TextInput(attrs={"tabindex": "5", "class": "form-control"}),
            "pos_y": forms.TextInput(attrs={"tabindex": "6", "class": "form-control"}),
            "pos_z": forms.TextInput(attrs={"tabindex": "7", "class": "form-control"}),
            "staff": forms.Select(attrs={"tabindex": "8", "class": "form-control"}),
        }


class InvoiceCreateForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = (
            "company",
            "billing_person",
            "rental_start_date",
            "rental_end_date",
            "staff",
        )
        exclude = ["billing_status"]
        widgets = {
            "rental_start_date": forms.DateInput(
                attrs={"tabindex": "1", "class": "form-control"}
            ),
            "rental_end_date": forms.DateInput(
                attrs={"tabindex": "2", "class": "form-control"}
            ),
            "company": forms.Select(attrs={"tabindex": "3", "class": "form-control"}),
            "billing_person": forms.Select(
                attrs={"tabindex": "4", "class": "form-control"}
            ),
            "staff": forms.Select(attrs={"tabindex": "5", "class": "form-control"}),
        }

    def clean_company(self):
        company = self.cleaned_data["company"]
        if "クサリク" in company.name:
            raise forms.ValidationError(
                "「クサリク」を含む取引先は選択できなくなりました（取引停止）"
            )
        return company
