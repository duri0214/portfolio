from requests.auth import HTTPBasicAuth
import requests

BASE_URL = "https://henojiya.atlassian.com/rest/api/3/issue/{issueIdOrKey}/changelog"
MAIL = 'yoshitakaOkada0214@gmail.com'
TOKEN = '3VMlKlzfKiIzOzhsmUrCEA8E'


def retrieve_tickets():
    issue_id_or_key = 'REICAGEO-25'
    url = f"https://henojiya.atlassian.com/rest/api/3/dashboard"
    headers = {
        "Accept": "application/json"
    }
    response = requests.get(
        url=url,
        headers=headers,
        auth=HTTPBasicAuth(MAIL, TOKEN)
    )
    print(response.url)

    return response


if __name__ == '__main__':
    retrieve_tickets()
