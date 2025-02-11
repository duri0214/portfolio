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
