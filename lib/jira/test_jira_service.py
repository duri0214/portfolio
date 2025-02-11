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

    @patch("requests.get")
    def test_fetch_issues_with_assignee(self, mock_get):
        """
        Test fetch_issues when issues have an assigned assignee.
        """
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
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
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

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
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
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
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

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
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
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
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

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
