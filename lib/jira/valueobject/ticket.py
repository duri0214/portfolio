import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    key: str
    name: str


@dataclass(frozen=True)
class Issue:
    key: str
    name: str
    description: str

    def __post_init__(self):
        if not self._validate_issue_id(self.key):
            raise ValueError("Invalid issue id format!")

    @staticmethod
    def _validate_issue_id(issue_id: str):
        # The issue_id usually looks like "XYZ-1". Modify this regex for your needs
        pattern = r"[A-Z]+-\d+"
        if re.match(pattern, issue_id):
            return True
        return False
