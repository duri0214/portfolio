import re


class IssueId:
    def __init__(self, issue_id: str):
        if not self._validate_issue_id(issue_id):
            raise ValueError("Invalid issue id format!")
        self._issue_id = issue_id

    @staticmethod
    def _validate_issue_id(issue_id: str):
        # The issue_id usually looks like "XYZ-1". Modify this regex for your needs
        pattern = r"[A-Z]+-\d+"
        if re.match(pattern, issue_id):
            return True
        return False

    @property
    def value(self):
        return self._issue_id


class EmailAddress:
    def __init__(self, email: str):
        if not self._validate_email(email):
            raise ValueError("Invalid email format!")
        self._email = email

    @staticmethod
    def _validate_email(email: str):
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if re.match(pattern, email):
            return True
        return False

    @property
    def value(self):
        return self._email
