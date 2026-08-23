from enum import StrEnum


class AccountActivationStatus(StrEnum):
    """メール認証URLを検証した結果を表す。

    Attributes:
        VALID: 有効なURLで、本登録を完了できる状態。
        EXPIRED: 署名は有効だが、有効期限を過ぎた状態。
        INVALID: UIDまたは署名が不正、もしくは使用済みの状態。
    """

    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
