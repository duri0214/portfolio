from django import forms
from django.db import transaction

from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    Kingdom,
    NaturalMonument,
    Phylum,
    Species,
)


class TaxonomyBreedCreateForm(forms.Form):
    """
    分類階層と品種をまとめて登録するフォーム。

    既存の階層を選ぶか、新しい階層名を入力して、最終的に Breed を作成する。
    """

    kingdom = forms.ModelChoiceField(
        label="既存の界",
        queryset=Kingdom.objects.none(),
        required=False,
        empty_label="新しく作る",
    )
    kingdom_name = forms.CharField(label="界の名前", max_length=255, required=False)
    kingdom_name_en = forms.CharField(label="界の英名", max_length=255, required=False)

    phylum = forms.ModelChoiceField(
        label="既存の門",
        queryset=Phylum.objects.none(),
        required=False,
        empty_label="新しく作る",
    )
    phylum_name = forms.CharField(label="門の名前", max_length=255, required=False)
    phylum_name_en = forms.CharField(label="門の英名", max_length=255, required=False)

    classification = forms.ModelChoiceField(
        label="既存の綱",
        queryset=Classification.objects.none(),
        required=False,
        empty_label="新しく作る",
    )
    classification_name = forms.CharField(
        label="綱の名前", max_length=255, required=False
    )
    classification_name_en = forms.CharField(
        label="綱の英名", max_length=255, required=False
    )

    family = forms.ModelChoiceField(
        label="既存の科",
        queryset=Family.objects.none(),
        required=False,
        empty_label="新しく作る",
    )
    family_name = forms.CharField(label="科の名前", max_length=255, required=False)
    family_name_en = forms.CharField(label="科の英名", max_length=255, required=False)

    genus = forms.ModelChoiceField(
        label="既存の属",
        queryset=Genus.objects.none(),
        required=False,
        empty_label="新しく作る",
    )
    genus_name = forms.CharField(label="属の名前", max_length=255, required=False)
    genus_name_en = forms.CharField(label="属の英名", max_length=255, required=False)

    species = forms.ModelChoiceField(
        label="既存の種",
        queryset=Species.objects.none(),
        required=False,
        empty_label="新しく作る",
    )
    species_name = forms.CharField(label="種の名前", max_length=255, required=False)
    species_name_en = forms.CharField(label="種の英名", max_length=255, required=False)

    breed_name = Breed.form_field("name")
    breed_name_kana = Breed.form_field("name_kana")
    breed_image = Breed.form_field("image")
    breed_remark = Breed.form_field("remark", widget=forms.Textarea(attrs={"rows": 3}))
    natural_monument = Breed.form_field("natural_monument", empty_label="指定なし")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kingdom"].queryset = Kingdom.objects.order_by("name")
        self.fields["phylum"].queryset = Phylum.objects.select_related(
            "kingdom"
        ).order_by("kingdom__name", "name")
        self.fields["classification"].queryset = Classification.objects.select_related(
            "phylum"
        ).order_by("phylum__kingdom__name", "phylum__name", "name")
        self.fields["family"].queryset = Family.objects.select_related(
            "classification"
        ).order_by("classification__phylum__kingdom__name", "name")
        self.fields["genus"].queryset = Genus.objects.select_related("family").order_by(
            "family__classification__phylum__kingdom__name", "name"
        )
        self.fields["species"].queryset = Species.objects.select_related(
            "genus"
        ).order_by("genus__family__classification__phylum__kingdom__name", "name")
        self.fields["natural_monument"].queryset = NaturalMonument.objects.order_by(
            "name"
        )
        for field_name in [
            "kingdom",
            "phylum",
            "classification",
            "family",
            "genus",
            "species",
            "natural_monument",
        ]:
            self.fields[field_name].label_from_instance = lambda obj: obj.name

        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        levels = [
            ("kingdom", "kingdom_name"),
            ("phylum", "phylum_name"),
            ("classification", "classification_name"),
            ("family", "family_name"),
            ("genus", "genus_name"),
            ("species", "species_name"),
        ]
        for select_field, name_field in levels:
            if cleaned_data.get(select_field) or cleaned_data.get(name_field):
                continue
            self.add_error(
                name_field,
                "既存データを選ぶか、新しい名前を入力してください。",
            )

        self._validate_existing_relations(cleaned_data)

        breed_name = cleaned_data.get("breed_name")
        if breed_name and Breed.objects.filter(name=breed_name).exists():
            self.add_error("breed_name", "この名前の品種は登録済みです。")

        return cleaned_data

    def _validate_existing_relations(self, cleaned_data):
        parent_child_fields = [
            ("kingdom", "phylum"),
            ("phylum", "classification"),
            ("classification", "family"),
            ("family", "genus"),
            ("genus", "species"),
        ]
        for parent_field, child_field in parent_child_fields:
            if cleaned_data.get(child_field) and not cleaned_data.get(parent_field):
                self.add_error(
                    child_field,
                    "上位階層を新規作成する場合は、この階層も新規入力してください。",
                )

        phylum = cleaned_data.get("phylum")
        kingdom = cleaned_data.get("kingdom")
        if phylum and kingdom and phylum.kingdom_id != kingdom.id:
            self.add_error("phylum", "選択した界に属する門を選んでください。")

        classification = cleaned_data.get("classification")
        if classification and phylum and classification.phylum_id != phylum.id:
            self.add_error("classification", "選択した門に属する綱を選んでください。")

        family = cleaned_data.get("family")
        if family and classification and family.classification_id != classification.id:
            self.add_error("family", "選択した綱に属する科を選んでください。")

        genus = cleaned_data.get("genus")
        if genus and family and genus.family_id != family.id:
            self.add_error("genus", "選択した科に属する属を選んでください。")

        species = cleaned_data.get("species")
        if species and genus and species.genus_id != genus.id:
            self.add_error("species", "選択した属に属する種を選んでください。")

    @transaction.atomic
    def save(self):
        kingdom = self._get_or_create_root(Kingdom, "kingdom")
        phylum = self._get_or_create_child(Phylum, "phylum", kingdom=kingdom)
        classification = self._get_or_create_child(
            Classification, "classification", phylum=phylum
        )
        family = self._get_or_create_child(
            Family, "family", classification=classification
        )
        genus = self._get_or_create_child(Genus, "genus", family=family)
        species = self._get_or_create_child(Species, "species", genus=genus)

        return Breed.objects.create(
            name=self.cleaned_data["breed_name"],
            name_kana=self.cleaned_data["breed_name_kana"],
            image=self.cleaned_data.get("breed_image") or "",
            remark=self.cleaned_data.get("breed_remark") or None,
            natural_monument=self.cleaned_data.get("natural_monument"),
            species=species,
        )

    def _get_or_create_root(self, model, prefix):
        selected = self.cleaned_data.get(prefix)
        if selected:
            return selected

        name = self.cleaned_data[f"{prefix}_name"]
        name_en = self.cleaned_data.get(f"{prefix}_name_en") or name
        instance, _ = model.objects.get_or_create(
            name=name,
            defaults={"name_en": name_en},
        )
        return instance

    def _get_or_create_child(self, model, prefix, **parent):
        selected = self.cleaned_data.get(prefix)
        if selected:
            return selected

        name = self.cleaned_data[f"{prefix}_name"]
        name_en = self.cleaned_data.get(f"{prefix}_name_en") or name
        instance, _ = model.objects.get_or_create(
            name=name,
            **parent,
            defaults={"name_en": name_en},
        )
        return instance


class BreedForm(forms.ModelForm):
    """
    既存の品種情報を編集するフォーム。
    """

    class Meta:
        model = Breed
        fields = [
            "species",
            "name",
            "name_kana",
            "image",
            "natural_monument",
            "remark",
        ]
        widgets = {
            "remark": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["species"].queryset = Species.objects.select_related(
            "genus__family__classification__phylum__kingdom"
        ).order_by(
            "genus__family__classification__phylum__kingdom__name",
            "genus__family__classification__phylum__name",
            "genus__family__classification__name",
            "genus__family__name",
            "genus__name",
            "name",
        )
        self.fields["natural_monument"].queryset = NaturalMonument.objects.order_by(
            "name"
        )
        self.fields["species"].label_from_instance = self._species_label
        self.fields["natural_monument"].label_from_instance = lambda obj: obj.name

        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def _species_label(self, species):
        genus = species.genus
        family = genus.family
        classification = family.classification
        phylum = classification.phylum
        kingdom = phylum.kingdom
        return (
            f"{kingdom.name} > {phylum.name} > {classification.name} > "
            f"{family.name} > {genus.name} > {species.name}"
        )
