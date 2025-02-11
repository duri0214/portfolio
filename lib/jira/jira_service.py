import os

import requests
from requests.auth import HTTPBasicAuth

from lib.jira.valueobject.ticket import ProjectVO

YOUR_DOMAIN = "henojiya"


def fetch_all_projects(base_url: str, email: str, api_token: str) -> list[ProjectVO]:
    """
    Fetch all projects from the JIRA API using `isLast` for termination.

    Args:
        base_url (str): The base URL of the JIRA instance.
        email (str): The email address for authentication.
        api_token (str): The API token for authentication.

    Returns:
        List[ProjectVO]: A list of ProjectVOs containing key and name.
    """
    url = f"{base_url}/rest/api/3/project/search"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}

    all_projects = []

    while url:
        response = requests.get(url, headers=headers, auth=auth)

        if response.status_code != 200:
            raise Exception(
                f"Failed to fetch projects: {response.status_code} {response.text}"
            )

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

        # 終了判定として `isLast` を使用
        if data.get("isLast", False):
            break

        # 次の URL を更新
        url = data.get("nextPage", None)

    return all_projects


if __name__ == "__main__":
    # API docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/#about
    # TODO: なんか消してあるissueも表示されるから、削除状態を知りたい
    # TODO: チケットを作成する機能を作る

    try:
        project_list = fetch_all_projects(
            base_url=f"https://{YOUR_DOMAIN}.atlassian.net",
            email=os.environ.get("EMAIL_HOST_USER"),
            api_token=os.environ.get("JIRA_API_KEY"),
        )
        print(project_list)
        print("process done")
    except Exception as e:
        print(f"Error: {e}")
