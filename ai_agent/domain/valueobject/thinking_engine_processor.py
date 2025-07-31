from typing import Literal

StatusType = Literal["success", "error", "warning", "reset"]


class TurnResult:
    """ターン処理の結果を表す値オブジェクト

    ThinkingEngineProcessorの処理結果を表現し、ステータス、メッセージ、
    次のエンティティなどの情報を保持します。
    """

    def __init__(
        self,
        status: StatusType,
        message: str,
        next_entity=None,
        response_text: str = "",
    ):
        """コンストラクタ

        Args:
            status: 処理結果のステータス ("success", "error", "warning", "reset")
            message: 処理結果に関するメッセージ
            next_entity: 次のターンで行動するエンティティ (オプション)
            response_text: 生成された応答テキスト (オプション)
        """
        self.status = status
        self.message = message
        self.next_entity = next_entity
        self.response_text = response_text

    def to_dict(self) -> dict:
        """辞書形式に変換

        Returns:
            処理結果を表す辞書
        """
        return {
            "status": self.status,
            "message": self.message,
            "next_entity": self.next_entity,
            "response_text": self.response_text,
        }

    @classmethod
    def success(cls, message: str, next_entity=None, response_text: str = ""):
        """成功結果を作成

        Args:
            message: 成功メッセージ
            next_entity: 次のエンティティ (オプション)
            response_text: 生成された応答テキスト (オプション)

        Returns:
            成功状態の結果オブジェクト
        """
        return cls("success", message, next_entity, response_text)

    @classmethod
    def error(cls, message: str):
        """エラー結果を作成

        Args:
            message: エラーメッセージ

        Returns:
            エラー状態の結果オブジェクト
        """
        return cls("error", message)

    @classmethod
    def warning(cls, message: str, next_entity=None):
        """警告結果を作成

        Args:
            message: 警告メッセージ
            next_entity: 次のエンティティ (オプション)

        Returns:
            警告状態の結果オブジェクト
        """
        return cls("warning", message, next_entity)

    @classmethod
    def reset(cls, message: str):
        """リセット結果を作成

        Args:
            message: リセットメッセージ

        Returns:
            リセット状態の結果オブジェクト
        """
        return cls("reset", message)
