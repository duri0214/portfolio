from gmarker.models import NearbyPlace


class NearbyPlaceRepository:

    @staticmethod
    def delete_by_category(category: int) -> bool:
        query = NearbyPlace.objects.filter(category=category)
        if query.count() > 0:
            query.delete()
            return True
        return False

    @staticmethod
    def bulk_create(objects: list[NearbyPlace]):
        NearbyPlace.objects.bulk_create(objects)
