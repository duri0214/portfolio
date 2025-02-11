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


class CreateIssuePayload:
    def __init__(
        self,
        description_text: str,
        issue_type_id: str,
        labels: list,
        parent_key: str,
        priority_id: str,
        project_id: str,
        reporter_id: str,
        summary: str,
    ):
        """
        チケット作成ペイロードデータのValue Object

        Args:
            description_text (str): チケットの説明文
            issue_type_id (str): イシュ―タイプのID
            labels (list): ラベル一覧
            parent_key (str): 親チケットのキー
            priority_id (str): 優先度のID
            project_id (str): プロジェクトのID
            reporter_id (str): 報告者のID
            summary (str): チケットの概要
        """
        self.description_text = description_text
        self.issue_type_id = issue_type_id
        self.labels = labels
        self.parent_key = parent_key
        self.priority_id = priority_id
        self.project_id = project_id
        self.reporter_id = reporter_id
        self.summary = summary

    def to_dict(self) -> dict:
        """
        ペイロードをJira API形式の辞書データに変換

        Returns:
            dict: Jira用のペイロードデータ
        """
        return {
            "fields": {
                "description": self._format_description(),
                "issuetype": {"id": self.issue_type_id},
                "labels": self.labels,
                "parent": {"key": self.parent_key},
                "priority": {"id": self.priority_id},
                "project": {"id": self.project_id},
                "reporter": {"id": self.reporter_id},
                "summary": self.summary,
            }
        }

    def _format_description(self) -> dict:
        """
        descriptionフィールドをJira標準のリッチテキスト形式に変換

        Returns:
            dict: リッチテキスト形式のdescriptionフィールド
        """
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": self.description_text,
                        }
                    ],
                }
            ],
        }
