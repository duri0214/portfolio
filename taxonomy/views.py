import json

from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import CreateView, UpdateView, TemplateView

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.node import NodeTree
from taxonomy.domain.repository.breed import BreedRepository
from taxonomy.domain.repository.chicken_observations import (
    ChickenObservationsRepository,
)


class IndexView(TemplateView):
    template_name = "taxonomy/index.html"

    def get_context_data(self, **kwargs):
        """
        コンテキスト内でBreedRepositoryとChickenObservationsRepositoryのデータを統合
        """
        context = super().get_context_data(**kwargs)

        # 1. Breed分類ツリーの取得
        tree = NodeTree(
            [BreedEntity(record) for record in BreedRepository.get_breed_hierarchy()]
        )
        context["data"] = json.dumps(tree.export(), ensure_ascii=False)

        # 2. 餌のデータと卵生産データを取得
        feed_usage = ChickenObservationsRepository.get_feed_usage_by_type()
        egg_production = ChickenObservationsRepository.get_egg_production_by_date()

        # JSON形式でテンプレートに渡す
        context["feed_usage"] = mark_safe(json.dumps(feed_usage, ensure_ascii=False))
        context["egg_production"] = mark_safe(
            json.dumps(egg_production, ensure_ascii=False)
        )

        # 必要に応じて他のリポジトリからデータを追加
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
