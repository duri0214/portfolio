from django.contrib.auth.models import User
from django.db import models

from lib.llm.valueobject.completion import RoleType
from llm_chat.domain.valueobject.chat import MessageDTO


class ChatLogs(models.Model):
    """
    LLM（大規模言語モデル）とのチャット履歴を保存するモデル。

    ユーザーの質問、システムプロンプト、AIの回答、生成された画像/音声のメタデータ、
    および実行モード（なぞなぞモード等）の状態を管理します。

    Attributes:
        user (ForeignKey): メッセージに関連付けられた Django の User インスタンス。
        role (CharField): メッセージの役割（SYSTEM, USER, ASSISTANT）。
        content (TextField): メッセージの本文（テキストまたは生成物のURL）。
        model_name (CharField): 使用された LLM のモデル名（例: gpt-4o, gemini-2.0-flash）。
        is_riddle (BooleanField): なぞなぞモードで作成されたメッセージかどうかのフラグ。
            ステートレスなHTTP通信において、過去の履歴から「なぞなぞ継続中か」を
            サーバー側で確実かつ永続的に判定するために、各メッセージに状態を保持させます。
            具体的には、最新の履歴が `is_riddle=True` かつ終了メッセージを含まない場合に
            「継続中」とみなすロジックの根拠データとなります。
        file (FileField): 生成された音声ファイルなどの保存先パス。
        created_at (DateTimeField): レコードの作成日時（自動設定）。
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=9,
        choices=[(x.name, x.value) for x in RoleType],
    )
    content = models.TextField()
    model_name = models.CharField(max_length=50, null=True, blank=True)
    is_riddle = models.BooleanField(default=False)
    file = models.FileField(upload_to="llm_chat/audios/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_message_dto(self):
        """
        このエンティティを MessageDTO に変換します。
        """

        return MessageDTO(
            user=self.user,
            role=RoleType(self.role),
            content=self.content,
            model_name=self.model_name,
            is_riddle=self.is_riddle,
            file_path=self.file.url if self.file else None,
            file_name=self.file.name if self.file else None,
        )
