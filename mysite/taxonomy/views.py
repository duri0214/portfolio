import json

from django.db.models import F
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from taxonomy.models import Kingdom, Breed


def exists(key_name: str, elements: list) -> bool:
    return_value = False
    for element in elements:
        if element["name"] == key_name:
            return_value = True
            break

    return return_value


class IndexView(ListView):
    model = Kingdom
    template_name = "taxonomy/index.html"

    def get_queryset(self):
        return Breed.objects \
            .annotate(
                kingdom_name=F('species__genus__family__classification__phylum__kingdom__name'),
                phylum_name=F('species__genus__family__classification__phylum__name'),
                classification_name=F('species__genus__family__classification__name'),
                family_name=F('species__genus__family__name'),
                genus_name=F('species__genus__name'),
                species_name=F('species__name'),
                breed_name=F('name'),
                breed_name_kana=F('name_kana'),
                natural_monument_name=F('natural_monument__name'),
                breed_tag=F('breedtags__tag__name')
            ) \
            .values(
                'kingdom_name', 'phylum_name', 'classification_name', 'family_name', 'genus_name', 'species_name',
                'breed_name', 'breed_name_kana', 'natural_monument_name', 'breed_tag'
            ) \
            .order_by(
                'kingdom_name', 'phylum_name', 'classification_name', 'family_name', 'genus_name', 'species_name',
                'breed_name', 'breed_name_kana', 'natural_monument_name', 'breed_tag'
            )

    def get_context_data(self, *, object_list=None, **kwargs):
        """
        See Also: https://github.com/EE2dev/d3-indented-tree#examples
        """
        context = super(IndexView, self).get_context_data(**kwargs)

        # kingdoms = set(list())
        # phylums = set(list())
        # classifications = set(list())
        # families = set(list())
        # genusies = set(list())
        # species = set(list())
        # breeds = set(list())
        # for row in self.get_queryset():
        #     kingdoms.add(row['kingdom_name'])
        #     phylums.add(row['phylum_name'])
        #     classifications.add(row['classification_name'])
        #     families.add(row['family_name'])
        #     genusies.add(row['genus_name'])
        #     species.add(row['species_name'])
        #     breeds.add(row['breed_name'])
        #
        # root = {"name": "root", "children": list()}
        # for i, kingdom in enumerate(kingdoms):
        #     root["children"] = [
        #         {"name": kingdom, "children": list()} for kingdom in kingdoms
        #     ]
        #     for ii, a_kingdom in enumerate(root["children"]):
        #         root["children"][i]["children"] = [
        #             {"name": phylum, "children": list()} for phylum in phylums
        #         ]
        #         for j, phylum in enumerate(phylums):
        #             root["children"][i]["children"][phylum] = [
        #                 {"name": classification, "children": list()} for classification in classifications
        #             ]
        #
        #             # for k, kingdom_child in enumerate(root_child["children"]):
        #             #     if not exists(phylum)
        # print(root)
        root = {
          "name": "World",
          "children": [
            {
              "name": "Asia",
              "population": 4436,
              "children": [
                {
                  "name": "China",
                  "population": 1420
                },
                {
                  "name": "India",
                  "population": 1369
                }
              ]
            },
            {
              "name": "Africa",
              "population": 1216
            },
            {
              "name": "Europe",
              "population": 739
            },
            {
              "name": "North America",
              "population": 579,
              "children": [
                {
                  "name": "USA",
                  "population": 329
                }
              ]
            },
            {
              "name": "South America",
              "population": 423
            },
            {
              "name": "Oceania",
              "population": 38
            }
          ]
        }

        context['data'] = json.dumps(root, ensure_ascii=False)

        return context


class KingdomCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class PhylumCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class ClassificationCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class FamilyCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class GenusCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class SpeciesCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class BreedCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class TagCreateView(CreateView):
    success_url = reverse_lazy("txo:index")


class BreedTagUpdateView(UpdateView):
    success_url = reverse_lazy("txo:index")
