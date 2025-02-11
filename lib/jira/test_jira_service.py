import unittest
from unittest.mock import patch, Mock

from requests.exceptions import HTTPError

from jira_service import JiraService


class TestJiraService(unittest.TestCase):
    def setUp(self):
        """
        Set up common test data for JiraService.
        """
        self.service = JiraService(
            domain="test-domain", email="test@example.com", api_token="test-token"
        )

    @patch("requests.get")
    def test_fetch_all_projects_success(self, mock_get):
        """
        Test fetch_all_projects with a successful response.
        """
        # Mock the API response for each page
        mock_response_1 = Mock()
        mock_response_1.json.return_value = {
            "values": [
                {"key": "TEST1", "name": "Test Project 1"},
                {"key": "TEST2", "name": "Test Project 2"},
            ],
            "isLast": False,
            "nextPage": "https://test-domain.atlassian.net/rest/api/3/project/search?page=2",
        }
        mock_response_1.status_code = 200
        mock_response_1.raise_for_status = Mock()

        mock_response_2 = Mock()
        mock_response_2.json.return_value = {
            "values": [
                {"key": "TEST3", "name": "Test Project 3"},
            ],
            "isLast": True,
        }
        mock_response_2.status_code = 200
        mock_response_2.raise_for_status = Mock()

        # Sequence of responses
        mock_get.side_effect = [mock_response_1, mock_response_2]

        # Execute the method
        result = self.service.fetch_all_projects()

        # Assertions
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].key, "TEST1")
        self.assertEqual(result[1].name, "Test Project 2")
        self.assertEqual(result[2].key, "TEST3")
        mock_get.assert_called()

    @patch("requests.get")
    def test_fetch_all_projects_auth_error(self, mock_get):
        """
        Test fetch_all_projects handling of 401 Unauthorized.
        """
        # Mock a 401 Unauthorized response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError(
            "401 Client Error: Unauthorized"
        )
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        # Assert that the exception is raised
        with self.assertRaises(HTTPError) as context:
            self.service.fetch_all_projects()

        self.assertIn("401 Client Error", str(context.exception))
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_fetch_all_projects_not_found(self, mock_get):
        """
        Test fetch_all_projects handling of 404 Not Found.
        """
        # Mock a 404 Not Found response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError(
            "404 Client Error: Not Found"
        )
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Assert that the exception is raised
        with self.assertRaises(HTTPError) as context:
            self.service.fetch_all_projects()

        self.assertIn("404 Client Error", str(context.exception))
        mock_get.assert_called_once()
