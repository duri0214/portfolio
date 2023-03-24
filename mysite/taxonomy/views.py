import json
from django.db.models import F
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.node import NodeTree
from taxonomy.models import Kingdom, Breed


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
        tree = NodeTree([BreedEntity(record) for record in self.get_queryset()])
        context['data'] = json.dumps(tree.export(), ensure_ascii=False)

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
