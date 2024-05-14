import os

import requests
from requests.auth import HTTPBasicAuth

from vietnam_research.domain.valueobject.jira import IssueId, EmailAddress

JIRA_API_URL = "https://henojiya.atlassian.net/rest/api/3/issue/"


def retrieve_specific_issue(issue_id: IssueId, mail: EmailAddress):
    url = f"{JIRA_API_URL}{issue_id.value}"
    headers = {"Accept": "application/json"}

    return requests.get(
        url=url,
        headers=headers,
        auth=requests.auth.HTTPBasicAuth(mail.value, os.environ.get("JIRA_TOKEN")),
    )


if __name__ == "__main__":
    issue = IssueId("HEN-1")
    email = EmailAddress("yoshitakaOkada0214@gmail.com")
    response = retrieve_specific_issue(issue, email)

    print(response)
