import json

from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import CreateView, FormView, UpdateView, TemplateView

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.node import NodeTree
from taxonomy.domain.repository.breed import BreedRepository
from taxonomy.domain.repository.chicken_observations import (
    ChickenObservationsRepository,
)
from taxonomy.forms import TaxonomyBreedCreateForm
from taxonomy.models import Classification, Family, Genus, Phylum, Species


class IndexView(TemplateView):
    template_name = "taxonomy/index.html"

    def get_context_data(self, **kwargs):
        """
        コンテキストデータを設定。
        主にBreedRepositoryを使用して分類データを取得し、
        Breed分類ツリーとしてテンプレートに提供する。
        """
        context = super().get_context_data(**kwargs)

        # Breed分類ツリーの取得
        tree = NodeTree(
            [BreedEntity(record) for record in BreedRepository.get_breed_hierarchy()]
        )
        context["data"] = json.dumps(tree.export(), ensure_ascii=False)

        return context


class ObservationView(TemplateView):
    template_name = "taxonomy/observation.html"

    def get_context_data(self, **kwargs):
        """
        Observationページのコンテキストデータを設定
        """
        context = super().get_context_data(**kwargs)

        # 餌の投入量と卵生産量データを取得
        feed_vs_egg = ChickenObservationsRepository.get_feed_vs_egg_production()
        context["feed_vs_egg"] = mark_safe(json.dumps(feed_vs_egg, ensure_ascii=False))

        # Feed Group別の産卵率データを取得
        context["feed_group_laying_rate"] = (
            ChickenObservationsRepository.get_feed_group_laying_rates_table()
        )

        return context


class TaxonomyBreedCreateView(FormView):
    """
    分類階層と品種を1画面で登録するビュー。

    既存階層の選択と不足階層の追加を同じフォームで扱い、保存後は
    分類ツリーを確認できるトップページへ戻す。
    """

    form_class = TaxonomyBreedCreateForm
    template_name = "taxonomy/breed_form.html"
    success_url = reverse_lazy("txo:index")

    def form_valid(self, form):
        breed = form.save()
        messages.success(self.request, f"{breed.name} を登録しました。")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hierarchy_json"] = json.dumps(
            self._build_hierarchy_options(), ensure_ascii=False
        )
        return context

    def _build_hierarchy_options(self):
        return {
            "phylum": [
                {"id": item.id, "name": item.name, "parent": item.kingdom_id}
                for item in Phylum.objects.order_by("kingdom_id", "name")
            ],
            "classification": [
                {"id": item.id, "name": item.name, "parent": item.phylum_id}
                for item in Classification.objects.order_by("phylum_id", "name")
            ],
            "family": [
                {"id": item.id, "name": item.name, "parent": item.classification_id}
                for item in Family.objects.order_by("classification_id", "name")
            ],
            "genus": [
                {"id": item.id, "name": item.name, "parent": item.family_id}
                for item in Genus.objects.order_by("family_id", "name")
            ],
            "species": [
                {"id": item.id, "name": item.name, "parent": item.genus_id}
                for item in Species.objects.order_by("genus_id", "name")
            ],
        }


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
