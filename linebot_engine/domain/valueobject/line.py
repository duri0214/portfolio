class WebhookEvent:
    """
    Notes: https://developers.line.biz/ja/reference/messaging-api/#webhook-event-objects
    """

    class Source:
        def __init__(self, source_dict):
            self.user_id = source_dict.get("userId")

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
