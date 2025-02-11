import unittest
from unittest.mock import patch, Mock

from requests import HTTPError

from jira_service import JiraService, IssueVO


class TestJiraServiceFetchIssues(unittest.TestCase):
    """
    JiraServiceクラスのfetch_issuesメソッドに関する単体テストを行います。
    - 各テストケースでは、APIのモックレスポンスを利用して、fetch_issuesの期待される動作を検証します。
    """

    def setUp(self):
        """
        各テストの実行前に共通のセットアップ処理を行います。
        JiraServiceのインスタンスを生成します。
        """
        self.service = JiraService(
            domain="test-domain", email="test@example.com", api_token="test-token"
        )

    @staticmethod
    def create_mock_response(json_data, status_code=200):
        """
        APIレスポンスをモックとして作成する共通のヘルパーメソッド。

        Args:
            json_data (dict): モックレスポンスとして返すJSONデータ
            status_code (int): HTTPステータスコード（デフォルトは200）

        Returns:
            Mock: モック化したレスポンスオブジェクト
        """
        mock_response = Mock()
        mock_response.json.return_value = json_data
        mock_response.status_code = status_code
        mock_response.raise_for_status = (
            Mock()
        )  # ステータスコードに応じた例外を発生させるモックを設定
        return mock_response

    @patch("requests.get")
    def test_fetch_issues_with_assignee(self, mock_get):
        """
        テスト内容:
            fetch_issuesが、「assignee」が指定されている課題を処理できることを確認する。
        シナリオ:
            - APIレスポンスに "assignee" フィールドが存在し、"displayName" を持つ場合をテストする。
            - "assignee" の情報が正しくIssueVOに設定されていることを検証する。
        """
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

        # 実行
        issues = self.service.fetch_issues("HEN")

        # 検証
        self.assertEqual(len(issues["HEN"]), 1)
        issue = issues["HEN"][0]
        self.assertIsInstance(issue, IssueVO)
        self.assertEqual(issue.assignee, "John Doe")
        self.assertEqual(issue.name, "Test Issue 1")
        self.assertEqual(issue.description, "No description")  # デフォルトの説明
        self.assertEqual(issue.priority, "High")
        self.assertEqual(issue.status, "To Do")

    @patch("requests.get")
    def test_fetch_issues_without_assignee(self, mock_get):
        """
        テスト内容:
            fetch_issuesが、「assignee」が指定されていない（None）の課題を処理できることを確認する。
        シナリオ:
            - APIレスポンスに "assignee" フィールドがNoneの場合をテストする。
            - IssueVOの「assignee」の値がNoneとなっていることを検証する。
        """
        mock_get.return_value = self.create_mock_response(
            {
                "issues": [
                    {
                        "key": "HEN-2",
                        "fields": {
                            "summary": "Test Issue 2",
                            "description": None,
                            "assignee": None,
                            "priority": {"name": "Medium"},
                            "status": {"name": "In Progress"},
                            "subtasks": [],
                        },
                    }
                ]
            }
        )

        # 実行
        issues = self.service.fetch_issues("HEN")

        # 検証
        self.assertEqual(len(issues["HEN"]), 1)
        issue = issues["HEN"][0]
        self.assertIsInstance(issue, IssueVO)
        self.assertIsNone(issue.assignee)  # AssigneeがNoneであることを検証
        self.assertEqual(issue.name, "Test Issue 2")
        self.assertEqual(issue.description, "No description")  # デフォルトの説明
        self.assertEqual(issue.priority, "Medium")
        self.assertEqual(issue.status, "In Progress")

    @patch("requests.get")
    def test_fetch_issues_with_multiple_issues(self, mock_get):
        """
        テスト内容:
            fetch_issuesが、複数の課題を正しく処理できることを確認する。
        シナリオ:
            - APIレスポンスに複数の課題が含まれる場合をテストする。
            - 各課題のフィールド（assignee, priority, statusなど）が正しく設定されていることを検証する。
        """
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

        # 実行
        issues = self.service.fetch_issues("HEN")

        # 検証
        self.assertEqual(len(issues["HEN"]), 2)

        # 課題1
        issue1 = issues["HEN"][0]
        self.assertEqual(issue1.assignee, "Jane Smith")
        self.assertEqual(issue1.name, "Issue 1")
        self.assertEqual(issue1.priority, "Low")
        self.assertEqual(issue1.status, "In Progress")

        # 課題2
        issue2 = issues["HEN"][1]
        self.assertIsNone(issue2.assignee)  # AssigneeがNoneであることを検証
        self.assertEqual(issue2.name, "Issue 2")
        self.assertEqual(issue2.priority, "High")
        self.assertEqual(issue2.status, "To Do")

    @patch("requests.get")
    def test_fetch_issues_with_invalid_project_key(self, mock_get):
        """
        fetch_issuesに無効なプロジェクトキーを渡した場合に正しく例外をスローするかを確認する。
        """
        # モックAPIの404エラー設定
        mock_response = self.create_mock_response({}, status_code=404)
        mock_response.raise_for_status.side_effect = HTTPError(
            "404 Client Error: Not Found"
        )
        mock_get.return_value = mock_response

        # 実行と例外の検証
        with self.assertRaises(HTTPError) as context:
            self.service.fetch_issues("INVALID")  # 存在しないプロジェクトキー

        # エラーメッセージを確認
        self.assertIn("404 Client Error", str(context.exception))
        mock_get.assert_called_once()
