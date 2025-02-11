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

    Attributes:
        key (str): The unique key of the sub-task.
        name (str): The name of the sub-task.
        status (str): The current status of the sub-task.
        priority (str): The priority of the sub-task.
    """

    key: str
    name: str
    status: str
    priority: str


@dataclass
class IssueVO:
    """
    Data class to represent an issue.

    Attributes:
        key (str): The unique key of the issue.
        name (str): The title or summary of the issue.
        description (str): The detailed description of the issue.
        priority (str): The priority of the issue.
        assignee (str): The display name of the assigned user.
        status (str): The current status of the issue.
        sub_tasks (list[SubTaskVO]): The list of sub-tasks associated with the issue.
    """

    key: str
    name: str
    description: str
    priority: str
    assignee: str
    status: str
    sub_tasks: list[SubTaskVO]
