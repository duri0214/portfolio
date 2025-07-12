from dataclasses import dataclass


@dataclass
class ModerationCategory:
    """
    モデレーションカテゴリを表すValue Object

    Args:
        name: カテゴリ名（例: "hate", "harassment", "violence"）
    """

    name: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("Category name cannot be empty")


@dataclass
class ModerationResult:
    """
    モデレーション結果を表すValue Object

    Args:
        blocked: モデレーションによりブロックされたかどうか
        message: ブロック時にユーザーに表示するエラーメッセージ
                例: "申し訳ありませんが、その内容は適切ではないため、お答えできません。"
                    "現在、安全性チェックが利用できません。しばらくしてから再度お試しください。"
        categories: OpenAI Moderation APIでフラグされたカテゴリのリスト
    """

    blocked: bool
    message: str = ""
    categories: list[ModerationCategory] | None = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = []
