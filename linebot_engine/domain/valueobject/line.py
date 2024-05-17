class WebhookEvent:
    def __init__(self, event: dict):
        self.type = event.get("type")
        self.timestamp = event.get("timestamp")
        self.source = event.get("source")
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
