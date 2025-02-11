import os

import requests
from requests.auth import HTTPBasicAuth

from lib.jira.valueobject.ticket import ProjectVO, IssueVO, SubTaskVO


class JiraService:
    """
    Service class for interacting with the JIRA API.
    """

    def __init__(self, domain: str, email: str, api_token: str):
        """
        Initialize the JiraService with domain, email, and API token.

        Args:
            domain (str): The JIRA domain (e.g., "your-domain").
            email (str): The email address for authentication.
            api_token (str): The API token for authentication.
        """
        self.base_url = f"https://{domain}.atlassian.net"
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
                issue_key = issue.get("key", "unknown")
                fields = issue.get("fields", {})

                # Parse description field, handling structured "content" format
                issue_description = "No description"
                raw_description = fields.get("description")
                if isinstance(raw_description, dict) and raw_description.get("content"):
                    issue_description = self._parse_content_field(
                        raw_description.get("content")
                    )

                # Process sub-tasks
                sub_tasks = []
                for sub_task in issue.get("fields", {}).get("sub-tasks", []):
                    sub_task_key = sub_task.get("outwardIssue", {}).get(
                        "key", "unknown"
                    )
                    sub_task_status = (
                        sub_task.get("outwardIssue", {})
                        .get("fields", {})
                        .get("status", {})
                        .get("name", "unknown")
                    )
                    sub_tasks.append(
                        SubTaskVO(key=sub_task_key, status=sub_task_status)
                    )

                # Create IssueVO
                issue_obj = IssueVO(
                    key=issue_key, description=issue_description, sub_tasks=sub_tasks
                )

                # Add issue to the dictionary under the correct project key
                if project_key not in issues_by_project:
                    issues_by_project[project_key] = []
                issues_by_project[project_key].append(issue_obj)

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
    # TODO: なんか消してあるissueも表示されるから、削除状態を知りたい
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

            for project, project_issues in issues.items():
                print(f"Project: {project}")
                for issue_xxx in project_issues:
                    print(f"  Issue Key: {issue_xxx.key}")
                    print(f"    Description: {issue_xxx.description}")
                    print(f"    Sub-Tasks:")
                    for sub_task_xxx in issue_xxx.sub_tasks:
                        print(f"        Sub-Task Key: {sub_task_xxx.key}")
                        print(f"        Status: {sub_task_xxx.status}")

        print("process done")
    except requests.exceptions.HTTPError as http_err:
        print(f"[HTTP Error] {http_err}")
