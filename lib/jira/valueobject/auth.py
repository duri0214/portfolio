import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailAddress:
    email: str

    def __post_init__(self):
        if not self._validate_email(self.email):
            raise ValueError("Invalid email format!")

    @staticmethod
    def _validate_email(email: str):
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if re.match(pattern, email):
            return True
        return False
