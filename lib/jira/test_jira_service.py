import unittest
from unittest.mock import patch, Mock

from jira_service import JiraService, IssueVO


class TestJiraServiceFetchIssues(unittest.TestCase):
    """
    Unit tests for the fetch_issues method of JiraService.
    """

    def setUp(self):
        """
        Common setup for the tests.
        """
        self.service = JiraService(
            domain="test-domain", email="test@example.com", api_token="test-token"
        )

    @staticmethod
    def create_mock_response(json_data, status_code=200):
        """
        Helper method to create a mock response object.

        Args:
            json_data (dict): The JSON data to return in the response.
            status_code (int): The HTTP status code for the response.

        Returns:
            Mock: A mocked response object.
        """
        mock_response = Mock()
        mock_response.json.return_value = json_data
        mock_response.status_code = status_code
        mock_response.raise_for_status = Mock()
        return mock_response

    @patch("requests.get")
    def test_fetch_issues_with_assignee(self, mock_get):
        """
        Test fetch_issues when issues have an assigned assignee.
        """
        # Use the helper to create a mock response
        mock_get.return_value = self.create_mock_response(
            {
                "issues": [
                    {
                        "key": "HEN-1",
                        "fields": {
                            "summary": "Test Issue 1",
                            "description": None,
                            "assignee": {"displayName": "John Doe"},
                            "priority": {"name": "High"},
                            "status": {"name": "To Do"},
                            "subtasks": [],
                        },
                    }
                ]
            }
        )

        # Execute
        issues = self.service.fetch_issues("HEN")

        # Assertions
        self.assertEqual(len(issues["HEN"]), 1)
        issue = issues["HEN"][0]
        self.assertIsInstance(issue, IssueVO)
        self.assertEqual(issue.assignee, "John Doe")
        self.assertEqual(issue.name, "Test Issue 1")
        self.assertEqual(issue.description, "No description")  # Default description
        self.assertEqual(issue.priority, "High")
        self.assertEqual(issue.status, "To Do")

    @patch("requests.get")
    def test_fetch_issues_without_assignee(self, mock_get):
        """
        Test fetch_issues when issues do not have an assignee (assignee is None).
        """
        # Use the helper to create a mock response
        mock_get.return_value = self.create_mock_response(
            {
                "issues": [
                    {
                        "key": "HEN-2",
                        "fields": {
                            "summary": "Test Issue 2",
                            "description": None,
                            "assignee": None,  # 'assignee' is explicitly None
                            "priority": {"name": "Medium"},
                            "status": {"name": "In Progress"},
                            "subtasks": [],
                        },
                    }
                ]
            }
        )

        # Execute
        issues = self.service.fetch_issues("HEN")

        # Assertions
        self.assertEqual(len(issues["HEN"]), 1)
        issue = issues["HEN"][0]
        self.assertIsInstance(issue, IssueVO)
        self.assertIsNone(issue.assignee)  # Assignee should be None
        self.assertEqual(issue.name, "Test Issue 2")
        self.assertEqual(issue.description, "No description")  # Default description
        self.assertEqual(issue.priority, "Medium")
        self.assertEqual(issue.status, "In Progress")

    @patch("requests.get")
    def test_fetch_issues_with_multiple_issues(self, mock_get):
        """
        Test fetch_issues when multiple issues are returned.
        """
        # Use the helper to create a mock response
        mock_get.return_value = self.create_mock_response(
            {
                "issues": [
                    {
                        "key": "HEN-3",
                        "fields": {
                            "summary": "Issue 1",
                            "assignee": {"displayName": "Jane Smith"},
                            "priority": {"name": "Low"},
                            "status": {"name": "In Progress"},
                            "subtasks": [],
                        },
                    },
                    {
                        "key": "HEN-4",
                        "fields": {
                            "summary": "Issue 2",
                            "assignee": None,
                            "priority": {"name": "High"},
                            "status": {"name": "To Do"},
                            "subtasks": [],
                        },
                    },
                ]
            }
        )

        # Execute
        issues = self.service.fetch_issues("HEN")

        # Assertions
        self.assertEqual(len(issues["HEN"]), 2)

        # Issue 1
        issue1 = issues["HEN"][0]
        self.assertEqual(issue1.assignee, "Jane Smith")
        self.assertEqual(issue1.priority, "Low")
        self.assertEqual(issue1.status, "In Progress")

        # Issue 2
        issue2 = issues["HEN"][1]
        self.assertIsNone(issue2.assignee)  # Assignee is None
        self.assertEqual(issue2.priority, "High")
        self.assertEqual(issue2.status, "To Do")
