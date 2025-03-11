from django.db.models import F

from taxonomy.models import Breed


class BreedRepository:
    """
    Breedモデルの分類データを取得するリポジトリクラス
    """

    @staticmethod
    def get_breed_hierarchy():
        """
        Breedの分類階層を取得するクエリ
        :return: 分類情報に基づいたリスト
        """
        return (
            Breed.objects.annotate(
                kingdom_name=F(
                    "species__genus__family__classification__phylum__kingdom__name"
                ),
                phylum_name=F("species__genus__family__classification__phylum__name"),
                classification_name=F("species__genus__family__classification__name"),
                family_name=F("species__genus__family__name"),
                genus_name=F("species__genus__name"),
                species_name=F("species__name"),
                breed_name=F("name"),
                breed_name_kana=F("name_kana"),
                natural_monument_name=F("natural_monument__name"),
                breed_tag=F("breedtags__tag__name"),
            )
            .values(
                "kingdom_name",
                "phylum_name",
                "classification_name",
                "family_name",
                "genus_name",
                "species_name",
                "breed_name",
                "breed_name_kana",
                "natural_monument_name",
                "breed_tag",
            )
            .order_by(
                "kingdom_name",
                "phylum_name",
                "classification_name",
                "family_name",
                "genus_name",
                "species_name",
                "breed_name",
                "breed_name_kana",
                "natural_monument_name",
                "breed_tag",
            )
        )
