import json

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.node import NodeTree
from taxonomy.domain.repository.breed import BreedRepository
from taxonomy.models import Kingdom


class IndexView(ListView):
    model = Kingdom
    template_name = "taxonomy/index.html"

    def get_queryset(self):
        return BreedRepository.get_breed_hierarchy()

    def get_context_data(self, *, object_list=None, **kwargs):
        """
        See Also: https://github.com/EE2dev/d3-indented-tree#examples
        """
        context = super(IndexView, self).get_context_data(**kwargs)
        tree = NodeTree([BreedEntity(record) for record in self.get_queryset()])
        context["data"] = json.dumps(tree.export(), ensure_ascii=False)

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
