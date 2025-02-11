import os

import requests
from requests.auth import HTTPBasicAuth

from lib.jira.valueobject.ticket import ProjectVO


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

    def fetch_all_projects(self) -> list[ProjectVO]:
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


if __name__ == "__main__":
    # API docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/#about
    # TODO: なんか消してあるissueも表示されるから、削除状態を知りたい
    # TODO: チケットを作成する機能を作る

    # JIRA configuration: Replace with actual values or environment variables
    YOUR_DOMAIN = os.getenv("YOUR_DOMAIN", "henojiya")
    EMAIL = os.getenv("EMAIL_HOST_USER")
    API_TOKEN = os.getenv("JIRA_API_KEY")

    jira_service = JiraService(domain=YOUR_DOMAIN, email=EMAIL, api_token=API_TOKEN)

    try:
        projects = jira_service.fetch_all_projects()
        print(projects)
        print("process done")
    except requests.exceptions.HTTPError as http_err:
        print(f"[HTTP Error] {http_err}")
