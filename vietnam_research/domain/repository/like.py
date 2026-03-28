from django.db.models import Count

from vietnam_research.models import Articles, Likes


class LikeRepository:
    """
    「いいね！」機能のリポジトリクラス。
    記事に対するいいねの登録・削除、存在確認、集計などDB操作を担当します。
    """

    @staticmethod
    def get_article(article_id) -> Articles:
        """指定したIDの記事を取得します。"""
        return Articles.objects.get(pk=article_id)

    @staticmethod
    def like_exists(user, article) -> bool:
        """指定したユーザーが記事に「いいね！」済みか確認します。"""
        return Likes.objects.filter(user=user, articles=article).exists()

    @staticmethod
    def create_like(user, article) -> Likes:
        """記事に「いいね！」を登録します。"""
        return Likes.objects.create(user=user, articles=article)

    @staticmethod
    def delete_like(user, article):
        """記事の「いいね！」を解除します。"""
        Likes.objects.filter(user=user, articles=article).delete()

    @staticmethod
    def count_article_likes(article):
        """記事の総「いいね！」数を集計します。"""
        return Likes.objects.filter(articles=article).aggregate(
            likes_count=Count("id")
        )["likes_count"]
