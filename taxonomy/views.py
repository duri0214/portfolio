import json

from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.node import NodeTree
from taxonomy.domain.repository.breed import BreedRepository
from taxonomy.domain.repository.chicken_observations import (
    ChickenObservationsRepository,
)
from taxonomy.domain.valueobject.livestock_distribution import (
    build_livestock_distribution_dashboard,
)
from taxonomy.forms import BreedForm, TaxonomyBreedCreateForm
from taxonomy.models import Breed, Classification, Family, Genus, Phylum, Species


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
        livestock_dashboard = build_livestock_distribution_dashboard()
        context["livestock_dashboard"] = livestock_dashboard
        context["livestock_distribution_json"] = livestock_dashboard.to_payload()

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
    登録した品種の詳細ページへ遷移する。
    """

    form_class = TaxonomyBreedCreateForm
    template_name = "taxonomy/breed_form.html"

    def form_valid(self, form):
        self.breed = form.save()
        messages.success(self.request, f"{self.breed.name} を登録しました。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("txo:breed_detail", kwargs={"pk": self.breed.pk})

    def form_invalid(self, form):
        messages.error(
            self.request, "登録できませんでした。入力内容を確認してください。"
        )
        return super().form_invalid(form)

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


class BreedListView(ListView):
    """
    品種レコードを分類階層付きで一覧表示するビュー。
    """

    model = Breed
    template_name = "taxonomy/breed_list.html"
    context_object_name = "breeds"

    def get_queryset(self):
        return Breed.objects.select_related(
            "species__genus__family__classification__phylum__kingdom",
            "natural_monument",
        ).order_by(
            "species__genus__family__classification__phylum__kingdom__name",
            "species__genus__family__classification__phylum__name",
            "species__genus__family__classification__name",
            "species__genus__family__name",
            "species__genus__name",
            "species__name",
            "name",
        )


class BreedDetailView(DetailView):
    """
    1件の品種レコードと分類階層を表示するビュー。
    """

    model = Breed
    template_name = "taxonomy/breed_detail.html"
    context_object_name = "breed"
    queryset = Breed.objects.select_related(
        "species__genus__family__classification__phylum__kingdom",
        "natural_monument",
    )


class BreedUpdateView(UpdateView):
    """
    既存の品種レコードを編集するビュー。
    """

    model = Breed
    form_class = BreedForm
    template_name = "taxonomy/breed_edit.html"
    context_object_name = "breed"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"{self.object.name} を更新しました。")
        return response

    def get_success_url(self):
        return reverse_lazy("txo:breed_detail", kwargs={"pk": self.object.pk})


class BreedDeleteView(DeleteView):
    """
    品種レコードを確認画面経由で削除するビュー。
    """

    model = Breed
    template_name = "taxonomy/breed_confirm_delete.html"
    context_object_name = "breed"
    success_url = reverse_lazy("txo:breed_list")
    queryset = Breed.objects.select_related(
        "species__genus__family__classification__phylum__kingdom"
    )

    def form_valid(self, form):
        name = self.object.name
        response = super().form_valid(form)
        messages.success(self.request, f"{name} を削除しました。")
        return response


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
