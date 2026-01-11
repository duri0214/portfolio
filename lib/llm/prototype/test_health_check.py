import unittest
from unittest.mock import patch, MagicMock
import os
import json
from lib.llm.prototype.llm_health_check import LLMHealthCheck, Status, CheckResult


class TestLLMHealthCheck(unittest.TestCase):
    """
    LLMHealthCheck クラスの機能をテストするためのクラス。
    環境変数のバリデーション、接続エラーのハンドリング、モデル互換性のチェックなどを検証します。
    """

    def setUp(self):
        """
        各テストの前に実行されるセットアップ処理。
        新しい LLMHealthCheck インスタンスを作成します。
        """
        self.checker = LLMHealthCheck()

    @staticmethod
    def _get_check_result(summary, name):
        """
        指定された名前のチェック結果をサマリーから取得します。
        """
        return next(r for r in summary["checks"] if r["name"] == name)

    def _assert_status(self, summary, name, expected_status):
        """
        指定された名前のチェック結果のステータスを検証します。
        """
        res = self._get_check_result(summary, name)
        self.assertEqual(res["status"], expected_status.value)
        return res

    @patch.dict(os.environ, {}, clear=True)
    def test_environment_variables_empty(self):
        """
        環境変数が空の場合のテスト。
        必須のAPIキーが見つからない場合に ERROR ステータスが返ることを確認します。
        """
        self.checker.check_environment_variables()
        summary = self.checker.get_summary()

        # OpenAI, Gemini, Azure は必須なので ERROR になるはず
        self._assert_status(summary, "Env: OPENAI_API_KEY", Status.ERROR)
        self._assert_status(summary, "Env: GEMINI_API_KEY", Status.ERROR)
        self._assert_status(summary, "Env: AZURE_OPENAI_API_KEY", Status.ERROR)
        self._assert_status(summary, "Env: AZURE_OPENAI_ENDPOINT", Status.ERROR)

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "invalid-key",
            "GEMINI_API_KEY": "short",
            "AZURE_OPENAI_API_KEY": "not-hex-32-chars-long-at-all!!!!",
        },
        clear=True,
    )
    def test_environment_variables_invalid_format(self):
        """
        環境変数の形式が不正な場合のテスト。
        正規表現にマッチしないキーが指定された場合に WARNING ステータスが返ることを確認します。
        """
        self.checker.check_environment_variables()
        summary = self.checker.get_summary()

        self._assert_status(summary, "Env: OPENAI_API_KEY", Status.WARNING)
        self._assert_status(summary, "Env: GEMINI_API_KEY", Status.WARNING)
        self._assert_status(summary, "Env: AZURE_OPENAI_API_KEY", Status.WARNING)

    @patch("openai.OpenAI")
    @patch("openai.AzureOpenAI")
    def test_endpoints_invalid_connection(self, mock_azure, mock_openai):
        """
        エンドポイントへの接続が失敗する場合のテスト。
        APIサーバーからのエラーを適切にキャッチし、ERROR ステータスを返すことを確認します。
        ※テストでは実際にAPIを呼び出さず、mockを使用して課金を完全に回避しています。
        """
        # Mocking the client to raise an error
        mock_instance = mock_openai.return_value
        mock_instance.models.list.side_effect = Exception("Connection refused")

        mock_azure_instance = mock_azure.return_value
        mock_azure_instance.models.list.side_effect = Exception(
            "Azure Connection refused"
        )

        # Set env for Azure to avoid skipping
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-proj-DUMMY-KEY-FOR-TESTING-PURPOSES-WHICH-IS-LONG-ENOUGH",
                "GEMINI_API_KEY": "AIza-DUMMY-KEY-FOR-TESTING-PURPOSES-31x",
                "AZURE_OPENAI_API_KEY": "REPLACE-WITH-32-HEX-CHARS-DUMMY",
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            },
        ):
            self.checker.check_endpoints()
            summary = self.checker.get_summary()

            openai_res = self._assert_status(summary, "Endpoint: OpenAI", Status.ERROR)
            self.assertIn("Connection refused", openai_res["message"])

            gemini_res = self._assert_status(summary, "Endpoint: Gemini", Status.ERROR)
            self.assertIn("Connection refused", gemini_res["message"])

            azure_res = self._assert_status(
                summary, "Endpoint: AzureOpenAI", Status.ERROR
            )
            self.assertIn("Azure Connection refused", azure_res["message"])

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-proj-DUMMY-KEY-FOR-TESTING-PURPOSES-WHICH-IS-LONG-ENOUGH",
            "AZURE_OPENAI_API_KEY": "REPLACE-WITH-32-HEX-CHARS-DUMMY",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
        },
        clear=True,
    )
    @patch("openai.OpenAI")
    @patch("openai.AzureOpenAI")
    def test_compatibility_missing_models(self, mock_azure, mock_openai):
        """
        利用可能なモデルリストに必要なモデルが含まれていない場合のテスト。
        期待されるモデル（gpt-4oなど）が見つからない場合に WARNING ステータスを返すことを確認します。
        ※テストでは実際にAPIを呼び出さず、mockを使用して課金を完全に回避しています。
        """
        mock_instance = mock_openai.return_value
        # 返回一个不包含期待モデルのリスト
        mock_instance.models.list.return_value = [
            MagicMock(id="gpt-3.5-turbo"),
            MagicMock(id="whisper-1"),
        ]

        mock_azure_instance = mock_azure.return_value
        mock_azure_instance.models.list.return_value = [
            MagicMock(id="gpt-35-turbo-dev"),
        ]

        self.checker.check_model_compatibility()
        summary = self.checker.get_summary()

        openai_comp = self._assert_status(
            summary, "Model Permission/Availability (OpenAI)", Status.WARNING
        )
        self.assertIn("Missing: gpt-4o", openai_comp["message"])

        azure_comp = self._assert_status(
            summary, "Model Permission/Availability (AzureOpenAI)", Status.WARNING
        )
        self.assertIn("Missing: gpt-4o", azure_comp["message"])

    def test_json_output(self):
        """
        結果サマリーが正しくJSON形式にシリアライズできることを確認します。
        """
        self.checker.add_result(
            CheckResult("Test", Status.OK, "Message", {"key": "val"})
        )
        summary = self.checker.get_summary()
        json_str = json.dumps(summary)
        self.assertIsInstance(json_str, str)
        decoded = json.loads(json_str)
        self.assertEqual(decoded["checks"][0]["name"], "Test")


if __name__ == "__main__":
    unittest.main()
