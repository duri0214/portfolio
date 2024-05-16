import os

from jira import JIRA, JIRAError

from vietnam_research.domain.valueobject.jira import (
    EmailAddress,
    Project,
    Issue,
)

JIRA_SERVER = "https://henojiya.atlassian.net"


def get_all_projects(mail: EmailAddress) -> list[Project]:
    jira_token = os.environ.get("JIRA_TOKEN")
    jira_instance = JIRA(JIRA_SERVER, basic_auth=(mail.value, jira_token))

    return [Project(x.key, x.name) for x in jira_instance.projects()]


def get_all_issues(mail: EmailAddress) -> list[Issue]:
    jira_token = os.environ.get("JIRA_TOKEN")
    jira_instance = JIRA(JIRA_SERVER, basic_auth=(mail.value, jira_token))

    temp = jira_instance.search_issues("project=HEN", maxResults=False)
    return [Issue(x.key, x.fields.summary, x.fields.description) for x in temp]


# TODO: チケットを作成する機能を作る
def retrieve_specific_issue(issue_key: str, mail: EmailAddress) -> Issue:
    jira_token = os.environ.get("JIRA_TOKEN")
    jira_instance = JIRA(JIRA_SERVER, basic_auth=(mail.value, jira_token))

    try:
        temp = jira_instance.issue(issue_key)
        return Issue(temp.key, temp.fields.summary, temp.fields.description)
    except JIRAError as e:
        raise ValueError(e.text)


if __name__ == "__main__":
    email = EmailAddress(os.environ.get("EMAIL_HOST_USER"))
    project_list = get_all_projects(email)
    for project in project_list:
        print(project)

    issue_list = get_all_issues(email)
    print(issue_list)

    retrieve_the_issue = retrieve_specific_issue("HEN-1", email)
    print(retrieve_the_issue)
