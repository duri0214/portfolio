class WebhookEvent:
    """
    Notes: https://developers.line.biz/ja/reference/messaging-api/#webhook-event-objects
    """

    class _Source:
        """
        type: user or group

        Notes: 3人以上でトークを利用することを「グループトーク」という
          ※1対1のトーク中に友だちを誘って会話することを「複数人トーク」というが、現在は、グループトークに機能が統合されているらしい
        """

        def __init__(self, source_dict):
            self.type = source_dict.get("type")
            self.group_id = source_dict.get("groupId")
            self.user_id = source_dict.get("userId")

        def is_user(self):
            return self.type == "user"

        def is_group(self):
            return self.type == "group"

    class _Message:
        class Emoji:
            def __init__(self, emoji):
                """
                index: テキストの先頭を0とした、textプロパティ内の絵文字の開始位置
                length: LINE絵文字の文字列の長さ。LINE絵文字 `(hello)` であれば、7
                productId: LINE絵文字の集合を示すプロダクトID
                emojiId: プロダクトID内のLINE絵文字のID
                  productId, emojiId は https://developers.line.biz/ja/docs/messaging-api/emoji-list/ を参照
                """
                self.index = emoji.get("index")
                self.length = emoji.get("length")
                self.product_id = emoji.get("productId")
                self.emoji_id = emoji.get("emojiId")

        class _Mention:
            """
            Message.textプロパティにメンションが含まれる場合のみ、Messageクラスに含まれる
            """

            class Mentionee:
                def __init__(self, mentionee):
                    """
                    index: テキストの先頭を0とした、textプロパティ内のメンションの開始位置。
                    length: メンションの長さ。@exampleであれば、8
                    type: メンションの対象 ["user": ユーザー, "all": グループ全体]
                    userId: メンションされたユーザーのユーザーID。プロフィール情報を取得することに、ユーザーが同意しているときにのみ含まれる
                    quotedMessageId: 引用されたメッセージのメッセージID。過去のメッセージを引用している場合にのみ含まれる
                    """
                    self.index = mentionee.get("index")
                    self.length = mentionee.get("length")
                    self.type = mentionee.get("type")
                    self.user_id = mentionee.get("userId")
                    self.quoted_message_id = mentionee.get("quotedMessageId")

            def __init__(self, mention):
                self.mentionees = [
                    self.Mentionee(m) for m in mention.get("mentionees", [])
                ]

        def __init__(self, message):
            """
            id: メッセージID
            text: エンドユーザーがLINE絵文字を送信した場合は、(hello)や(love)のように、LINE絵文字が文字列で含まれます。
              エンドユーザーがメンションした場合は、`@example`のように、送信相手のLINEアカウントの表示名が文字列で含まれます。
              メンションの詳細は、mentionプロパティで確認できます。
              i.e. `@All @example Good Morning!! (love)`
            quoteToken: メッセージの引用トークン
            emojis: textプロパティに含まれる絵文字の配列
            mention: extプロパティに含まれるメンションの情報

            Notes: text に絵文字もメンションも含まれるので、 emojis, mention で文字加工する必要はなさそう
            """
            self.id = message.get("id")
            self.type = message.get("type")
            self.text = message.get("text")
            self.quote_token = message.get("quoteToken")
            self.emojis = [self.Emoji(e) for e in message.get("emojis", [])]
            self.mention = (
                self._Mention(message.get("mention", {}))
                if "mention" in message
                else None
            )

    class _Follow:
        """
        Notes: 初めて友だち追加されたとき、isUnblockedの値はfalseとなります。
          これは、ユーザがブロックから解除されたのではなく、新たに友だちに追加されたことを示します
          一方、ユーザがブロックから解除された場合、isUnblockedの値はtrueとなります。
          これは、ユーザがあなたの公式アカウントのブロックを解除したことを示します
        """

        def __init__(self, follow_event):
            self.is_unblocked = follow_event.get("isUnblocked", False)

    def __init__(self, event):
        """
        replyToken: イベントに対して応答メッセージを送る際に使用する応答トークン
        type: message or follow or unfollow and more
          https://developers.line.biz/ja/reference/messaging-api/#message-event を参照
        mode: active or standby チャネルの状態。standbyのときは、メッセージの送信を控えてください
        timestamp: イベントの発生時刻 UNIX時間（ミリ秒）。再送されたWebhookの場合でも当初時刻を示す
        source: イベントの送信元情報を含むユーザー、グループトーク。アカウントの連携に失敗した場合含まれない
        webhookEventId: WebhookイベントID。Webhookイベントを一意に識別するためのID。ULID形式の文字列
        deliveryContext: isRedelivery が True なら再送されたことを示す
        event_data: メッセージかフォローアクションかなどによって別のオブジェクトをロードする
        """
        self.reply_token = event.get("replyToken")
        self.type = event.get("type")
        self.mode = event.get("mode")
        self.timestamp = event.get("timestamp")
        self.source = self._Source(event.get("source"))
        self.webhook_event_id = event.get("webhookEventId")
        self.delivery_context = event.get("deliveryContext")
        self.event_data = self._parse_event_data(event)

    def _parse_event_data(self, event):
        if self.is_message():
            return self._Message(event.get("message", {}))
        elif self.is_follow() or self.is_unfollow():
            return self._Follow(event.get("follow", {}))
        else:
            raise ValueError(f"Unsupported event type: {self.type}")

    def is_message(self):
        return self.type == "message"

    def is_follow(self):
        return self.type == "follow"

    def is_unfollow(self):
        return self.type == "unfollow"
