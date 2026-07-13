from django.db.models import F

from taxonomy.domain.valueobject.taxonomy_hierarchy import TAXONOMY_HIERARCHY_RANKS
from taxonomy.models import Breed


class BreedRepository:
    """
    Breedモデルの分類データを取得するリポジトリクラス
    """

    HIERARCHY_SOURCE_FIELDS = {
        "kingdom": "species__genus__family__classification__phylum__kingdom",
        "phylum": "species__genus__family__classification__phylum",
        "classification": "species__genus__family__classification",
        "family": "species__genus__family",
        "genus": "species__genus",
        "species": "species",
        "breed": "",
    }

    @staticmethod
    def get_breed_hierarchy():
        """
        Breedの分類階層を取得するクエリ
        :return: 分類情報に基づいたリスト
        """
        hierarchy_annotations = BreedRepository._build_hierarchy_annotations()
        hierarchy_value_fields = BreedRepository._build_hierarchy_value_fields()
        hierarchy_name_fields = [f"{rank}_name" for rank in TAXONOMY_HIERARCHY_RANKS]
        return (
            Breed.objects.annotate(
                **hierarchy_annotations,
                breed_name_kana=F("name_kana"),
                natural_monument_name=F("natural_monument__name"),
                breed_tag=F("breedtags__tag__name"),
            )
            .values(
                *hierarchy_value_fields,
                "breed_name_kana",
                "natural_monument_name",
                "breed_tag",
            )
            .order_by(
                *hierarchy_name_fields,
                "breed_name_kana",
                "natural_monument_name",
                "breed_tag",
            )
        )

    @staticmethod
    def _build_hierarchy_annotations():
        annotations = {}
        for rank in TAXONOMY_HIERARCHY_RANKS:
            source_path = BreedRepository.HIERARCHY_SOURCE_FIELDS[rank]
            if source_path:
                annotations[f"{rank}_source_id"] = F(f"{source_path}__id")
                annotations[f"{rank}_name"] = F(f"{source_path}__name")
            else:
                annotations[f"{rank}_source_id"] = F("id")
                annotations[f"{rank}_name"] = F("name")
        return annotations

    @staticmethod
    def _build_hierarchy_value_fields():
        fields = []
        for rank in TAXONOMY_HIERARCHY_RANKS:
            fields.append(f"{rank}_source_id")
            fields.append(f"{rank}_name")
        return fields
