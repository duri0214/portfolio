from soil_analysis.models import Land


class LandRepository:
    @staticmethod
    def find_land_by_id(land_id: int) -> Land:
        return Land.objects.get(pk=land_id)

    @staticmethod
    def exists_by_name(name: str) -> bool:
        """
        名前を指定して圃場が存在するか確認します

        Args:
            name: 圃場名

        Returns:
            bool: 存在する場合はTrue
        """
        return Land.objects.filter(name=name).exists()
