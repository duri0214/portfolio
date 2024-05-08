from django.db.models import F

from vietnam_research.models import Articles, BasicInformation


class MarketRepository:
    @staticmethod
    def get_articles(login_id):
        # TODO: 試作なのでデザインの都合上「投稿」は3つしか取得しない
        return (
            Articles.with_state(login_id)
            .annotate(user_name=F("user__email"))
            .order_by("-created_at")[:3]
        )

    @staticmethod
    def get_basic_info():
        return BasicInformation.objects.order_by("id").values("item", "description")
