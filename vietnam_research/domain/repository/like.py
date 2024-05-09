from django.db.models import Count, QuerySet

from vietnam_research.models import Articles, Likes


class LikeRepository:
    @staticmethod
    def get_article(article_id) -> QuerySet:
        return Articles.objects.get(pk=article_id)

    @staticmethod
    def like_exists(user, article) -> bool:
        return Likes.objects.filter(user=user, articles=article).exists()

    @staticmethod
    def create_like(user, article) -> QuerySet:
        return Likes.objects.create(user=user, articles=article)

    @staticmethod
    def delete_like(user, article):
        Likes.objects.filter(user=user, articles=article).delete()

    @staticmethod
    def count_article_likes(article):
        return Likes.objects.filter(articles=article).aggregate(
            likes_count=Count("id")
        )["likes_count"]
