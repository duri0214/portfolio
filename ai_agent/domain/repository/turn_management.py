from datetime import datetime

from ai_agent.models import Entity, ActionTimeline, Message


class TurnManagementRepository:
    @staticmethod
    def get_all_entities():
        """
        システム内のすべてのエンティティを取得します。

        Returns:
            QuerySet[Entity]: すべてのエンティティを含むクエリセット
        """
        return Entity.objects.all()

    @staticmethod
    def get_timelines_ordered_by_next_turn():
        """
        next_turnフィールドの昇順で並べられたActionTimelineを取得します。
        これにより、次に行動するエンティティの順序を決定できます。

        Returns:
            QuerySet[ActionTimeline]: next_turnで昇順ソートされたActionTimelineのクエリセット
        """
        return ActionTimeline.objects.order_by("next_turn")

    @staticmethod
    def update_or_create_action_timeline(entity, defaults):
        """
        指定されたエンティティのActionTimelineレコードを更新または作成します。

        Args:
            entity (Entity): 対象のエンティティ
            defaults (dict): 更新または作成時に設定するフィールド値の辞書

        Returns:
            tuple: (ActionTimeline, bool) - 作成/更新されたオブジェクトと、作成されたかどうかを示すブール値
        """
        return ActionTimeline.objects.update_or_create(entity=entity, defaults=defaults)

    @staticmethod
    def get_action_timeline(entity):
        """
        特定のエンティティのActionTimelineを取得します。

        Args:
            entity (Entity): タイムラインを取得するエンティティ

        Returns:
            ActionTimeline or None: エンティティのアクションタイムライン、存在しない場合はNone
        """
        return ActionTimeline.objects.filter(entity=entity).first()

    @staticmethod
    def update_next_turn(action_timeline, increment):
        """
        ActionTimelineのnext_turn値を指定された増分で更新します。

        エンティティが行動した後、次の行動までの間隔を設定するために使用します。

        Args:
            action_timeline (ActionTimeline): 更新するタイムラインオブジェクト
            increment (float): next_turnに加算する増分値
        """
        action_timeline.next_turn += increment
        action_timeline.save()

    @staticmethod
    def create_message(entity, content):
        """
        エンティティのメッセージを作成し、データベースに保存します。

        Args:
            entity (Entity): メッセージを送信するエンティティ
            content (str): メッセージの内容

        Returns:
            Message: 作成されたメッセージオブジェクト
        """
        return Message.objects.create(
            entity=entity,
            message_content=content,
            created_at=datetime.now(),
        )
