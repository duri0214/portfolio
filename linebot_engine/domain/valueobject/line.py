class WebhookEvent:
    """
    Notes: https://developers.line.biz/ja/reference/messaging-api/#webhook-event-objects
    """

    class Source:
        def __init__(self, source_dict):
            self.type = source_dict.get("type")
            self.user_id = source_dict.get("userId")
            self.group_id = source_dict.get("groupId")
            self.room_id = source_dict.get("roomId")

        def is_user(self):
            return self.type == "user"

        def is_group(self):
            """
            Notes: 3人以上でトークを利用することを「グループトーク」という
            """
            return self.type == "group"

        def is_room(self):
            """
            Notes: 1対1のトーク中に友だちを誘って会話することを「複数人トーク」という
                   ※現在は、グループトークに機能が統合されているらしい
            """
            return self.type == "room"

    def __init__(self, event: dict):
        self.type = event.get("type")
        self.timestamp = event.get("timestamp")
        if isinstance(event.get("source"), dict):
            self.source = self.Source(event.get("source"))
        else:
            self.source = None
        self.reply_token = event.get("replyToken")
        self.mode = event.get("mode")
        self.webhook_event_id = event.get("webhookEventId")
        self.delivery_context = event.get("deliveryContext")
        self.message = event.get("message")

    def is_message(self):
        return self.type == "message"

    def is_follow(self):
        return self.type == "follow"

    def is_unfollow(self):
        return self.type == "unfollow"
