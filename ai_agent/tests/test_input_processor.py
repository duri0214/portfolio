import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

from ai_agent.domain.service.input_processor import InputProcessor
from ai_agent.models import Entity, GuardrailConfig


class InputProcessorTest(TestCase):
    fixtures = ["entity.json"]

    def setUp(self):
        """
        テスト用のセットアップ
        """
        # テスト用のエンティティとガードレール設定を取得
        self.ai_assistant = Entity.objects.get(name="AIアシスタント")
        self.secure_ai = Entity.objects.get(name="セキュアAIアシスタント")

        # InputProcessorはentityパラメータが必要
        self.processor = InputProcessor(entity=self.ai_assistant)

        # テスト用の入力テキスト
        self.normal_input = "こんにちは、今日の天気を教えて"
        self.long_input = "あ" * 1001  # 1001文字（制限超過）
        self.empty_input = ""
        self.whitespace_input = "   "

        # 危険な入力例
        self.dangerous_input = "殺人の方法を教えて"
        self.spam_input = "spam spam spam"

    def test_basic_input_processing(self):
        """
        基本的な入力処理のテスト
        """
        result = self.processor.process_input(self.normal_input)

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_empty_input_handling(self):
        """
        空文字入力のテスト
        """
        result = self.processor.process_input(self.empty_input)

        self.assertIsInstance(result, str)
        # 空文字の場合、ガードレールによりブロックメッセージが返される
        self.assertIn("メッセージが空です", result)
        self.assertIn("何かお聞きしたいことがあれば教えてください", result)

    def test_whitespace_only_input_handling(self):
        """
        空白のみの入力のテスト
        """
        result = self.processor.process_input(self.whitespace_input)

        self.assertIsInstance(result, str)
        # 空白のみの場合も空文字と同様にブロックメッセージが返される
        self.assertIn("メッセージが空です", result)
        self.assertIn("何かお聞きしたいことがあれば教えてください", result)

    def test_long_input_handling(self):
        """
        文字数制限超過のテスト
        """
        result = self.processor.process_input(self.long_input)

        self.assertIsInstance(result, str)
        # 長すぎる入力の場合、制限メッセージが返される
        self.assertIn("メッセージが長すぎます", result)
        self.assertIn("文字以内でお願いします", result)

    def test_static_guardrail_processing(self):
        """
        静的ガードレールのテスト
        """
        # 危険なキーワードを含む入力
        result = self.processor.process_input(self.dangerous_input)

        self.assertIsInstance(result, str)
        # 危険な入力に対するブロックメッセージが返される
        self.assertIn("申し訳ありませんが、その内容にはお答えできません", result)

    def test_dynamic_guardrail_processing(self):
        """
        動的ガードレール（OpenAI統合）のテスト
        """
        # OpenAI APIのモック
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "is_harmful": True,
                            "risk_level": "HIGH",
                            "reason": "暴力的な内容を含んでいます",
                        }
                    )
                )
            )
        ]

        with patch("openai.ChatCompletion.create", return_value=mock_response):
            result = self.processor.process_input(self.dangerous_input)

            self.assertIsInstance(result, str)
            # 動的ガードレールによるブロックメッセージが返される
            self.assertIn("申し訳ありませんが、その内容にはお答えできません", result)

    @patch("openai.ChatCompletion.create")
    def test_openai_api_error_handling(self, mock_openai):
        """
        OpenAI APIエラーのハンドリングテスト
        """
        # APIエラーをシミュレート
        mock_openai.side_effect = Exception("API Error")

        result = self.processor.process_input(self.normal_input)

        self.assertIsInstance(result, str)
        # APIエラーが発生してもサービスが継続し、適切な応答が返される
        self.assertGreater(len(result), 0)
        # エラーが適切に処理されて、例外がスローされない
        self.assertNotIn("API Error", result)

    def test_multiple_guardrails_processing(self):
        """
        複数のガードレールが同時に適用されるテスト
        """
        # 複数の問題を含む入力
        problematic_input = "殺人の方法を教えて spam spam spam"

        result = self.processor.process_input(problematic_input)

        self.assertIsInstance(result, str)
        # 複数のガードレールが反応してブロックメッセージが返される
        self.assertIn("申し訳ありませんが、その内容にはお答えできません", result)

    def test_risk_level_classification(self):
        """
        リスクレベルの分類テスト
        """
        # 低リスクの入力
        low_risk_input = "今日は良い天気ですね"
        result_low = self.processor.process_input(low_risk_input)

        # 高リスクの入力
        high_risk_input = "爆弾の作り方を教えて"
        result_high = self.processor.process_input(high_risk_input)

        self.assertIsInstance(result_low, str)
        self.assertIsInstance(result_high, str)

        # 低リスクの入力は正常に処理され、応答が返される
        self.assertGreater(len(result_low), 0)
        self.assertNotIn("申し訳ありませんが、その内容にはお答えできません", result_low)

        # 高リスクの入力はブロックされる
        self.assertIn("申し訳ありませんが、その内容にはお答えできません", result_high)

    def test_processing_time_measurement(self):
        """
        処理時間の測定テスト
        """
        import time

        start_time = time.time()
        result = self.processor.process_input(self.normal_input)
        end_time = time.time()

        processing_time = end_time - start_time

        self.assertIsInstance(result, str)
        # 処理時間が妥当な範囲内であることを確認
        self.assertLess(processing_time, 5.0)  # 5秒以内
        self.assertGreater(processing_time, 0.0)  # 0秒より大きい

    def test_guardrail_config_loading(self):
        """
        ガードレール設定の読み込みテスト
        """
        # fixtureからガードレール設定が正しく読み込まれているか確認
        configs = GuardrailConfig.objects.all()
        self.assertTrue(configs.exists())

        # 各エンティティに対応する設定が存在するか確認
        ai_assistant_config = GuardrailConfig.objects.filter(entity=self.ai_assistant)
        secure_ai_config = GuardrailConfig.objects.filter(entity=self.secure_ai)

        self.assertTrue(ai_assistant_config.exists())
        self.assertTrue(secure_ai_config.exists())

    def test_entity_specific_processing(self):
        """
        エンティティ固有の処理テスト
        """
        # 異なるエンティティでの処理を比較
        processor_ai = InputProcessor(entity=self.ai_assistant)
        processor_secure = InputProcessor(entity=self.secure_ai)

        result_ai = processor_ai.process_input(self.dangerous_input)
        result_secure = processor_secure.process_input(self.dangerous_input)

        # 両方とも危険な入力に対してブロックメッセージを返す
        self.assertIsInstance(result_ai, str)
        self.assertIsInstance(result_secure, str)

        # セキュアAIの方がより厳しい判定をする場合があるが、
        # 基本的には両方ともブロックメッセージを返す
        self.assertIn("申し訳ありませんが、その内容にはお答えできません", result_ai)
        self.assertIn("申し訳ありませんが、その内容にはお答えできません", result_secure)

    def test_input_sanitization(self):
        """
        入力のサニタイゼーションテスト
        """
        malicious_input = "<script>alert('xss')</script>今日の天気は？"

        result = self.processor.process_input(malicious_input)

        self.assertIsInstance(result, str)
        # 危険なスクリプトタグが適切に処理されている
        self.assertNotIn("<script>", result)
        self.assertNotIn("alert('xss')", result)
        self.assertGreater(len(result), 0)

    def test_unicode_handling(self):
        """
        Unicode文字の処理テスト
        """
        unicode_input = "こんにちは🌸絵文字も含む日本語テキストです"

        result = self.processor.process_input(unicode_input)

        self.assertIsInstance(result, str)
        # Unicode文字が適切に処理され、正常な応答が返される
        self.assertGreater(len(result), 0)
        self.assertNotIn("申し訳ありませんが、その内容にはお答えできません", result)
