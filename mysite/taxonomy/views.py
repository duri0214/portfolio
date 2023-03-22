import json
from django.db.models import F
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from taxonomy.models import Kingdom, Breed


def get_child_node(anchor_node: dict, needle: str) -> dict:
    """
    anchor_node の children に needle がいれば、その child_node を返す。いなければ新規dictを入れて、その child_node を返す

    Returns: dict
    """
    # TODO: Nodeクラスに置き換える A と B は返り値の型が違うだけで、処理は一緒なので整理する
    child_node = None
    is_exists = not not [child for child in anchor_node['children'] if child['name'] == needle]  # A
    if len(anchor_node['children']) > 0 and is_exists:
        for child in anchor_node['children']:  # B
            if child['name'] == needle:
                child_node = child
    else:
        child_node = {"name": needle, "children": []}
        anchor_node['children'].append(child_node)

    return child_node


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

        root = {"name": "root", "children": []}  # TODO: NodeTreeクラスに切り替える
        for row in self.get_queryset():
            kingdom = get_child_node(root, row['kingdom_name'])
            phylum = get_child_node(kingdom, row['phylum_name'])
            classification = get_child_node(phylum, row['classification_name'])
            family = get_child_node(classification, row['family_name'])
            genus = get_child_node(family, row['genus_name'])
            species = get_child_node(genus, row['species_name'])
            breed = get_child_node(species, row['breed_name'])

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
