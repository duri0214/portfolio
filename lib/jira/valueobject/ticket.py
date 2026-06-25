from dataclasses import dataclass


@dataclass
class ProjectVO:
    """
    Value Object (VO) to represent a JIRA project

    Attributes:
        key (str): The unique key of the project
        name (str): The name of the project
    """

    key: str
    name: str


@dataclass
class SubTaskVO:
    """
    Data class to represent subtasks of an issue

    Attributes:
        key (str): The unique key of the subtask
        name (str): The name of the subtask
        status (str): The current status of the subtask
        priority (str): The priority of the subtask
    """

    key: str
    name: str
    status: str
    priority: str


@dataclass
class IssueVO:
    """
    Data class to represent an issue

    Attributes:
        key (str): The unique key of the issue
        name (str): The title or summary of the issue
        description (str): The detailed description of the issue
        priority (str): The priority of the issue
        assignee (str): The display name of the assigned user
        status (str): The current status of the issue
        sub_tasks (list[SubTaskVO]): The list of subtasks associated with the issue
    """

    key: str
    name: str
    description: str
    priority: str
    assignee: str
    status: str
    sub_tasks: list[SubTaskVO]


@dataclass
class CreateIssuePayload:
    """
    Jiraチケット作成APIへ渡すフィールドを保持するValue Object。

    Attributes:
        summary: チケットの概要。
        project_key: Jiraプロジェクトのキー。
        issue_type_id: 課題タイプのID。
        description_text: チケットの説明文。
        labels: ラベル一覧。
        parent_key: 親チケットのキー。
        priority_id: 優先度のID。
        reporter_id: 報告者のアカウントID。
    """

    summary: str
    project_key: str
    issue_type_id: str
    description_text: str = ""
    labels: list[str] | None = None
    parent_key: str | None = None
    priority_id: str | None = None
    reporter_id: str | None = None

    def to_dict(self) -> dict:
        """
        ペイロードをJira API形式の辞書データに変換

        Returns:
            dict: Jira用のペイロードデータ
        """
        fields = {
            "issuetype": {"id": self.issue_type_id},
            "project": {"key": self.project_key},
            "summary": self.summary,
        }
        if self.description_text:
            fields["description"] = self._format_description()
        if self.labels:
            fields["labels"] = self.labels
        if self.parent_key:
            fields["parent"] = {"key": self.parent_key}
        if self.priority_id:
            fields["priority"] = {"id": self.priority_id}
        if self.reporter_id:
            fields["reporter"] = {"id": self.reporter_id}

        return {"fields": fields}

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


@dataclass
class UpdateIssuePayload:
    """
    Jiraチケット編集APIへ渡す更新フィールドを保持するValue Object。

    Attributes:
        summary: 更新後の概要。未指定なら送信しない。
        description_text: 更新後の説明文。未指定なら送信しない。
        labels: 更新後のラベル一覧。未指定なら送信しない。
        priority_id: 更新後の優先度ID。未指定なら送信しない。
    """

    summary: str | None = None
    description_text: str | None = None
    labels: list[str] | None = None
    priority_id: str | None = None

    def to_dict(self) -> dict:
        """
        更新ペイロードをJira API形式の辞書データに変換する。

        Returns:
            dict: Jira用の更新ペイロードデータ。
        """
        fields = {}
        if self.summary is not None:
            fields["summary"] = self.summary
        if self.description_text is not None:
            fields["description"] = self._format_description()
        if self.labels is not None:
            fields["labels"] = self.labels
        if self.priority_id is not None:
            fields["priority"] = {"id": self.priority_id}

        return {"fields": fields}

    def _format_description(self) -> dict:
        """
        descriptionフィールドをJira標準のリッチテキスト形式に変換する。

        Returns:
            dict: リッチテキスト形式のdescriptionフィールド。
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
