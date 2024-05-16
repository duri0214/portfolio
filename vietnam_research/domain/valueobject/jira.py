import re


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


class Project:
    def __init__(self, key: str, name: str):
        self.key = key
        self.name = name

    def __str__(self):
        return f"Project Key: {self.key}, Project Name: {self.name}"


class Issue:
    def __init__(self, key: str, name: str, description: str):
        if not self._validate_issue_id(key):
            raise ValueError("Invalid issue id format!")
        self.key = key
        self.name = name
        self.description = description

    def __str__(self):
        return f"Issue Key: {self.key}, Issue Name: {self.name}, Issue Description: {self.description}"

    @staticmethod
    def _validate_issue_id(issue_id: str):
        # The issue_id usually looks like "XYZ-1". Modify this regex for your needs
        pattern = r"[A-Z]+-\d+"
        if re.match(pattern, issue_id):
            return True
        return False
