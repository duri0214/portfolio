from unittest.mock import Mock, patch

from django.test import TestCase

from lib.llm.service.agent import ModerationService


class TestModerationService(TestCase):
    """
    ModerationServiceクラスのテストケース。

    このテストクラスは、OpenAI Moderation APIを使用したコンテンツ安全性チェック機能をテストします。

    テスト対象メソッド:
        - check_input_moderation: 入力テキストの安全性チェック
        - check_output_moderation: 出力テキストの安全性チェック
        - create_moderation_guardrail: 入力ガードレール関数の生成
        - create_output_moderation_guardrail: 出力ガードレール関数の生成

    テストシナリオ:
        1. 正常系: 安全なテキストの処理
        2. 異常系: 不適切なテキストの検出
        3. エラー系: API呼び出し失敗時の処理
        4. 厳格モード: strict_mode の動作確認
    """

    def setUp(self):
        self.service = ModerationService()
        self.entity_name = "テストエンティティ"
        self.safe_text = "こんにちは、お元気ですか？"
        self.unsafe_text = "暴力的な内容を含むテキスト"

        # モッククライアント生成
        self.mock_client = Mock()
        self.service.openai_client = self.mock_client

        # 安全なレスポンスのモック
        self.mock_safe_response = Mock()
        self.mock_safe_response.results = [Mock()]
        self.mock_safe_response.results[0].flagged = False
        self.mock_safe_response.results[0].categories.model_dump.return_value = {
            "violence": False,
            "hate": False,
            "harassment": False,
            "self-harm": False,
            "sexual": False,
            "sexual/minors": False,
            "violence/graphic": False,
            "hate/threatening": False,
            "harassment/threatening": False,
            "self-harm/intent": False,
            "self-harm/instructions": False,
        }

        # 危険なレスポンスのモック
        self.mock_unsafe_response = Mock()
        self.mock_unsafe_response.results = [Mock()]
        self.mock_unsafe_response.results[0].flagged = True
        self.mock_unsafe_response.results[0].categories.model_dump.return_value = {
            "violence": True,
            "hate": False,
            "harassment": False,
            "self-harm": False,
            "sexual": False,
            "sexual/minors": False,
            "violence/graphic": False,
            "hate/threatening": False,
            "harassment/threatening": False,
            "self-harm/intent": False,
            "self-harm/instructions": False,
        }

    def test_check_input_moderation_safe_content(self):
        """
        入力モデレーションの正常系テスト: 安全なコンテンツの処理

        シナリオ:
            1. 安全なテキストを入力として与える
            2. OpenAI Moderation APIが「問題なし」と判定
            3. サービスが「ブロックなし」のレスポンスを返す

        期待結果:
            - blocked = False
            - messageが空または未設定
            - categoriesが含まれない

        重要度: 高
        理由: 通常の安全なやり取りが正常に動作することを保証
        """
        self.mock_client.moderations.create.return_value = self.mock_safe_response

        # テスト実行
        result = self.service.check_input_moderation(
            self.safe_text, self.entity_name, strict_mode=False
        )

        # 結果検証
        self.assertFalse(result.blocked)
        self.assertEqual(result.message, "")
        self.assertNotIn("violence", [c.name for c in result.categories])

        # API呼び出しの検証
        self.mock_client.moderations.create.assert_called_once_with(
            model="text-moderation-latest", input=self.safe_text
        )

    def test_check_input_moderation_unsafe_content(self):
        """
        入力モデレーションの異常系テスト: 不適切なコンテンツの検出

        シナリオ:
            1. 不適切なテキストを入力として与える
            2. OpenAI Moderation APIが「問題あり」と判定
            3. サービスが「ブロックあり」のレスポンスを返す

        期待結果:
            - blocked = True
            - 適切なブロックメッセージが設定される
            - 違反カテゴリーが含まれる

        重要度: 高
        理由: 不適切なコンテンツが確実にブロックされることを保証
        """
        # モックレスポンスを設定
        self.mock_client.moderations.create.return_value = self.mock_unsafe_response

        # テスト実行
        result = self.service.check_input_moderation(
            self.unsafe_text, self.entity_name, strict_mode=False
        )

        # 結果検証
        self.assertTrue(result.blocked)
        self.assertIn(
            "申し訳ありませんが、その内容は適切ではないため、お答えできません",
            result.message,
        )
        self.assertIn(self.entity_name, result.message)
        self.assertIn("violence", [c.name for c in result.categories])
        self.assertEqual(len(result.categories), 1)

    def test_check_input_moderation_api_error_non_strict(self):
        """
        入力モデレーションのエラー系テスト: API呼び出し失敗時の処理（非厳格モード）

        シナリオ:
            1. OpenAI Moderation APIの呼び出しが失敗する
            2. strict_mode = False で実行
            3. エラーログが出力されるが、処理は継続される

        期待結果:
            - blocked = False (非厳格モードのため通す)
            - エラーログが出力される
            - ユーザーには影響しない

        重要度: 中
        理由: API障害時でもサービスが継続できることを保証
        """
        self.mock_client.moderations.create.side_effect = Exception("API Error")

        # ログのモック
        with patch("lib.llm.service.agent.logger") as mock_logger:
            # テスト実行
            result = self.service.check_input_moderation(
                self.safe_text, self.entity_name, strict_mode=False
            )

            # 結果検証
            self.assertFalse(result.blocked)
            self.assertEqual(result.message, "")

            # ログ出力の検証
            mock_logger.warning.assert_called_once()
            self.assertIn(
                "OpenAI Moderation API error", mock_logger.warning.call_args[0][0]
            )

    def test_check_input_moderation_api_error_strict(self):
        """
        入力モデレーションのエラー系テスト: API呼び出し失敗時の処理（厳格モード）

        シナリオ:
            1. OpenAI Moderation APIの呼び出しが失敗する
            2. strict_mode = True で実行
            3. エラー時もブロックされる

        期待結果:
            - blocked = True (厳格モードのため安全側に倒す)
            - 適切なエラーメッセージが設定される
            - ユーザーに一時的な利用不可を通知

        重要度: 高
        理由: 厳格モードでは安全性を最優先することを保証
        """
        # モックにエラーを仕込む
        self.mock_client.moderations.create.side_effect = Exception("API Error")

        # テスト実行
        result = self.service.check_input_moderation(
            self.safe_text, self.entity_name, strict_mode=True
        )

        # 結果検証
        self.assertTrue(result.blocked)
        self.assertIn("現在、安全性チェックが利用できません", result.message)
        self.assertIn(self.entity_name, result.message)

    def test_check_output_moderation_safe_content(self):
        """
        出力モデレーションの正常系テスト: 安全なコンテンツの処理

        シナリオ:
            1. AIが生成した安全なテキストを出力として与える
            2. OpenAI Moderation APIが「問題なし」と判定
            3. サービスが「ブロックなし」のレスポンスを返す

        期待結果:
            - blocked = False
            - 出力テキストがそのまま使用可能

        重要度: 高
        理由: 通常のAI応答が正常に出力されることを保証
        """
        self.mock_client.moderations.create.return_value = self.mock_safe_response

        # テスト実行
        result = self.service.check_output_moderation(self.safe_text, self.entity_name)

        # 結果検証
        self.assertFalse(result.blocked)
        self.assertEqual(result.message, "")

    def test_check_output_moderation_unsafe_content(self):
        """
        出力モデレーションの異常系テスト: 不適切なコンテンツの検出

        シナリオ:
            1. AIが生成した不適切なテキストを出力として与える
            2. OpenAI Moderation APIが「問題あり」と判定
            3. サービスが「ブロックあり」のレスポンスを返す

        期待結果:
            - blocked = True
            - 適切な代替メッセージが設定される
            - 元の不適切な出力は表示されない

        重要度: 高
        理由: AI応答が不適切な場合に確実にブロックされることを保証
        """
        # モックレスポンスを設定
        self.mock_client.moderations.create.return_value = self.mock_unsafe_response

        # テスト実行
        result = self.service.check_output_moderation(
            self.unsafe_text, self.entity_name
        )

        # 結果検証
        self.assertTrue(result.blocked)
        self.assertIn("適切な回答を生成できませんでした", result.message)
        self.assertIn(self.entity_name, result.message)

    def test_create_moderation_guardrail(self):
        """
        入力ガードレール関数生成のテスト

        シナリオ:
            1. create_moderation_guardrail メソッドでガードレール関数を生成
            2. 生成された関数が正しく動作する
            3. エンティティ名と厳格モードが正しく適用される

        期待結果:
            - 呼び出し可能な関数が返される
            - 関数実行時に適切なパラメータでモデレーションが行われる

        重要度: 中
        理由: Agents SDKとの統合機能が正常に動作することを保証
        """
        # モックレスポンスを設定
        self.mock_client.moderations.create.return_value = self.mock_unsafe_response

        # ガードレール関数の生成
        guardrail_func = self.service.create_moderation_guardrail(
            self.entity_name, strict_mode=True
        )

        # 関数が生成されることを確認
        self.assertTrue(callable(guardrail_func))

        # 生成された関数の実行テスト
        result = guardrail_func(None, None, self.safe_text)

        # 結果検証
        self.assertTrue(result["blocked"])

    def test_create_output_moderation_guardrail(self):
        """
        出力ガードレール関数生成のテスト

        シナリオ:
            1. create_output_moderation_guardrail メソッドでガードレール関数を生成
            2. 生成された関数が正しく動作する
            3. エンティティ名が正しく適用される

        期待結果:
            - 呼び出し可能な関数が返される
            - 関数実行時に適切なパラメータでモデレーションが行われる

        重要度: 中
        理由: Agents SDKとの統合機能が正常に動作することを保証
        """
        # モックレスポンスを設定
        self.mock_client.moderations.create.return_value = self.mock_unsafe_response

        # ガードレール関数の生成
        guardrail_func = self.service.create_output_moderation_guardrail(
            self.entity_name
        )

        # 関数が生成されることを確認
        self.assertTrue(callable(guardrail_func))

        # 生成された関数の実行テスト
        result = guardrail_func(None, None, self.unsafe_text)

        # 結果検証
        self.assertTrue(result["blocked"])
        self.assertIn(self.entity_name, result["message"])

    def test_service_initialization(self):
        """
        サービスの初期化テスト

        シナリオ:
            1. AIAgentModerationService のインスタンスが正常に作成される
            2. OpenAI クライアントが適切に設定される

        期待結果:
            - サービスインスタンスが作成される
            - openai_client 属性が存在する

        重要度: 低
        理由: 基本的な初期化が正常に行われることを保証
        """
        service = ModerationService()
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.openai_client)


class TestModerationServiceIntegration(TestCase):
    """
    ModerationService の統合テストケース

    このテストクラスは、実際の使用シナリオに近い形でのテストを行います。
    複数のメソッドが連携して動作することを確認します。

    注意: 実際のOpenAI APIは呼び出さず、すべてモックで実行します。
    """

    def setUp(self):
        """統合テスト用のセットアップ"""
        self.service = ModerationService()
        self.entity_name = "統合テスト用エンティティ"

        # モッククライアントの作成と差し替え
        self.mock_client = Mock()
        self.service.openai_client = self.mock_client

    def test_full_moderation_workflow(self):
        """
        完全なモデレーションワークフローのテスト

        シナリオ:
            1. 入力テキストのモデレーション
            2. 出力テキストのモデレーション
            3. 両方とも安全な場合の処理フロー

        期待結果:
            - 入力・出力ともにブロックされない
            - 正常な会話フローが実現される

        重要度: 高
        理由: 実際のユーザー体験に直結する統合動作を保証
        """
        # 安全なレスポンスを設定
        mock_safe_response = Mock()
        mock_safe_response.results = [Mock()]
        mock_safe_response.results[0].flagged = False
        self.mock_client.moderations.create.return_value = mock_safe_response

        # 入力モデレーションのテスト
        input_result = self.service.check_input_moderation(
            "こんにちは、今日はいい天気ですね", self.entity_name
        )
        self.assertFalse(input_result.blocked)

        # 出力モデレーションのテスト
        output_result = self.service.check_output_moderation(
            "はい、とても良い天気です。お出かけ日和ですね", self.entity_name
        )
        self.assertFalse(output_result.blocked)

        # API呼び出し回数の確認
        self.assertEqual(self.mock_client.moderations.create.call_count, 2)
