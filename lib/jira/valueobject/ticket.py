from dataclasses import dataclass


@dataclass
class ProjectVO:
    """
    Value Object (VO) to represent a JIRA project.

    Attributes:
        key (str): The unique key of the project.
        name (str): The name of the project.
    """

    key: str
    name: str


@dataclass
class SubTaskVO:
    """
    Data class to represent sub-tasks of an issue.
    """

    key: str
    status: str


@dataclass
class IssueVO:
    """
    Data class to represent an issue.
    """

    key: str
    description: str
    sub_tasks: list[SubTaskVO]
