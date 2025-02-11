import os

import requests
from requests import HTTPError
from requests.auth import HTTPBasicAuth

from lib.jira.valueobject.ticket import ProjectVO, IssueVO, SubTaskVO


class JiraService:
    """
    Service class for interacting with the JIRA API.
    """

    def __init__(self, domain: str = None, email: str = None, api_token: str = None):
        """
        Initialize the JiraService with domain, email, and API token.

        Args:
            domain (str): The JIRA domain (e.g., "your-domain").
            email (str): The email address for authentication.
            api_token (str): The API token for authentication.
        """
        missing_envs = []
        if not domain:
            missing_envs.append("YOUR_DOMAIN")
        if not email:
            missing_envs.append("EMAIL")
        if not api_token:
            missing_envs.append("API_TOKEN")

        if missing_envs:
            error_message = f"400 Bad Request: Missing required environment variable(s): {', '.join(missing_envs)}"
            raise HTTPError(error_message)

        self.base_url = f"https://{domain}.atlassian.net"
        # TODO: Basic認証の問題なのか401は出ない。OAuth 2.0化が必要か
        self.auth = HTTPBasicAuth(email, api_token)
        self.headers = {"Accept": "application/json"}

    def fetch_projects(self) -> list[ProjectVO]:
        """
        Fetch all projects from the JIRA API using `isLast` for termination.

        Returns:
            List[ProjectVO]: A list of ProjectVOs containing project key and name.

        Raises:
            HTTPError: If the HTTP request returns an error response.
        """
        url = f"{self.base_url}/rest/api/3/project/search"
        all_projects = []

        while url:
            response = requests.get(url, headers=self.headers, auth=self.auth)

            # Automatically raise an exception for HTTP error responses
            response.raise_for_status()

            # Parse the response JSON
            data = response.json()

            # Extract the necessary fields from each project in the 'values'
            for project in data.get("values", []):
                all_projects.append(
                    ProjectVO(
                        key=project.get("key", "invalid key"),
                        name=project.get("name", "invalid name"),
                    )
                )

            # Exit the loop if this is the last page
            if data.get("isLast", False):
                break

            # Update the URL for the next page
            url = data.get("nextPage", None)

        return all_projects

    def fetch_issues(self, project_key: str) -> dict[str, list[IssueVO]]:
        """
        Fetch all issues for a given project from the JIRA API.

        Args:
            project_key (str): The key of the project (e.g., "HSP").

        Returns:
            Dict[str, List[IssueVO]]: A dictionary with project keys as keys and lists of issues as values.

        Raises:
            HTTPError: If the HTTP request returns an error response.
        """
        url = f"{self.base_url}/rest/api/3/search"
        query = {
            "jql": f"project = {project_key} AND issuetype = Task",
            "maxResults": 50,  # Adjust as needed
            "fields": "key,issuetype,priority,assignee,status,description,summary,subtasks",
        }
        issues_by_project = {}

        while url:
            response = requests.get(
                url, headers=self.headers, auth=self.auth, params=query
            )

            # Automatically raise an exception for HTTP error responses
            response.raise_for_status()

            # Parse the response JSON
            data = response.json()

            # Extract issues
            for issue in data.get("issues", []):
                fields = issue.get("fields", {})
                issue_key = issue.get("key", "No issue key")

                # Check if the current issue is a regular issue or a subtask
                is_subtask = fields.get("issuetype", {}).get("subtask", False)
                issue_name = fields.get("summary", "No summary")
                issue_status = fields.get("status", {}).get("name", "No status")
                issue_priority = fields.get("priority", {}).get("name", "No priority")

                # "assignee" の処理: None なら None, そうでなければ displayName 取得
                issue_assignee = None
                if fields.get("assignee"):
                    issue_assignee = fields.get("assignee").get(
                        "displayName", "Unassigned"
                    )

                issue_description = "No description"

                # `description` が辞書形式の場合、正しく _parse_content_field を呼ぶ
                raw_description = fields.get("description")
                if isinstance(raw_description, dict) and raw_description.get("content"):
                    issue_description = self._parse_content_field(
                        raw_description.get("content")
                    )

                # If it's not a subtask, process as a regular issue (IssueVO)
                if not is_subtask:
                    sub_tasks = []
                    for sub_task in fields.get("subtasks", []):
                        sub_task_key = sub_task.get("key", "No sub-task")
                        sub_task_name = sub_task.get("fields").get(
                            "summary", "No summary"
                        )
                        sub_task_status = (
                            sub_task.get("fields", {})
                            .get("status", {})
                            .get("name", "No status")
                        )
                        sub_task_priority = (
                            sub_task.get("fields", {})
                            .get("priority", {})
                            .get("name", "No priority")
                        )
                        sub_tasks.append(
                            SubTaskVO(
                                key=sub_task_key,
                                name=sub_task_name,
                                status=sub_task_status,
                                priority=sub_task_priority,
                            )
                        )

                    issue_obj = IssueVO(
                        key=issue_key,
                        name=issue_name,
                        description=issue_description,
                        priority=issue_priority,
                        assignee=issue_assignee,
                        status=issue_status,
                        sub_tasks=sub_tasks,
                    )

                    # Add the issue object to the dictionary under the project key
                    if project_key not in issues_by_project:
                        issues_by_project[project_key] = []
                    issues_by_project.get(project_key).append(issue_obj)

            # Update the URL for the next page if available
            if "nextPage" in data:
                url = data["nextPage"]
            else:
                url = None

        return issues_by_project

    @staticmethod
    def _parse_content_field(content: list) -> str:
        """
        Helper function to extract text from the 'content' field in the description.

        Args:
            content (list): The 'content' field from the issue description.

        Returns:
            str: Extracted plain text description.
        """
        description_text = []

        for block in content:
            # Ensure the block has "type" and "content"
            if not isinstance(block, dict) or "content" not in block:
                continue

            for inner_block in block.get("content", []):
                # Look for 'text' in inner blocks
                if isinstance(inner_block, dict) and inner_block.get("type") == "text":
                    description_text.append(inner_block.get("text", ""))

        return " ".join(description_text)


if __name__ == "__main__":
    # API docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/#about
    # TODO: チケットを作成する機能を作る
    # APIキーが入ってなかったらraise
    # healthチェックして401ならraise
    # プロジェクト名が不正なら400
    # チケットを作成する
    # チケットを削除する
    # チケットを編集する

    # JIRA configuration: Replace with actual values or environment variables
    YOUR_DOMAIN = os.getenv("JIRA_YOUR_DOMAIN")
    EMAIL = os.getenv("EMAIL_HOST_USER")
    API_TOKEN = os.getenv("JIRA_API_KEY")

    jira_service = JiraService(domain=YOUR_DOMAIN, email=EMAIL, api_token=API_TOKEN)

    try:
        for pjt in jira_service.fetch_projects():
            print(pjt)
            issues = jira_service.fetch_issues(project_key=pjt.key)

            for project_xxx, project_issues in issues.items():
                print(f"Project: {project_xxx}")
                for issue_xxx in project_issues:
                    print(issue_xxx)

        print("process done")
    except requests.exceptions.HTTPError as http_err:
        print(f"[HTTP Error] {http_err}")
