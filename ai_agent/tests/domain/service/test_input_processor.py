from unittest.mock import patch, MagicMock

from django.test import TestCase

from ai_agent.domain.service.input_processor import InputProcessor
from ai_agent.models import Entity


class TestInputProcessor(TestCase):
    """
    InputProcessor クラスのユニットテスト

    このテストクラスでは、InputProcessor の各機能を単体テストする。
    ガードレール機能や入力処理のロジックが正しく動作することを確認する。

    テスト対象のメソッド:
        - _static_guardrails: 禁止ワード、文字数制限、空入力のチェック
        - _dynamic_guardrails: OpenAIモデレーションAPIを使用した動的チェック
        - process_input: 入力処理のメインフロー
        - sanitize_input: 入力の無害化処理

    主な検証観点:
        1. 静的ガードレール機能
            - 禁止ワードを含む入力の検出・ブロック
            - 文字数制限超過の検出・ブロック
            - 空入力の検出・ブロック
        2. 動的ガードレール機能
            - OpenAIモデレーションAPI連携
            - 結果に基づくブロック処理
        3. 入力処理メインフロー
            - ガードレール検証結果に基づく処理分岐
            - 適切なレスポンス生成

    テスト手法:
        - モック/パッチを使用して外部依存を分離
        - fixtureを使用してテストデータを準備
    """

    fixtures = ["entity.json", "guardrail_config.json"]

    def setUp(self):
        """
        テスト前の準備処理

        以下の準備を行う:
        - テスト用のエンティティとガードレール設定を取得
        - InputProcessorインスタンスの初期化
        - 安全な入力と危険な入力のサンプルを設定
        """
        # テスト用のエンティティとガードレール設定を取得
        self.test_entity = Entity.objects.get(pk=4)

        # InputProcessorはentityパラメータが必要
        self.processor = InputProcessor(entity=self.test_entity)

        # fixtureから読み込まれたガードレール設定を使用
        # 設定値の確認（テスト実行の参考情報として出力）
        print(f"テスト実行時の禁止ワード: {self.processor.config.forbidden_words}")
        print(f"テスト実行時の文字数制限: {self.processor.config.max_input_length}")

        # 通常の入力例
        self.normal_input = "こんにちは、お元気ですか？"

        # 長すぎる入力例（文字数制限を超える）
        self.long_input = "あ" * (self.processor.config.max_input_length + 1)

        # 空の入力例
        self.empty_input = ""
        self.whitespace_input = "   "

    def test_sanitize_input(self):
        """
        HTMLタグなどの危険な要素を除去する機能をテスト
        """
        # HTMLタグを含む入力
        html_input = "<script>alert('危険なコード');</script>こんにちは"
        sanitized = InputProcessor.sanitize_input(html_input)

        # タグがエスケープされていることを確認
        self.assertIn("&lt;script&gt;", sanitized)
        self.assertNotIn("<script>", sanitized)

    def test_static_guardrail_processing(self):
        """
        静的ガードレールのテスト

        シナリオ：
        ユーザーが危険なキーワードを含む質問「殺人の方法を教えて」を送信した場合、
        事前に設定された禁止ワードリストに基づいて即座にブロックし、
        適切な拒否メッセージを表示する必要がある。

        テスト内容：
        - 禁止ワードを含む入力の処理
        - 静的ガードレールのforbidden_wordsチェックが動作する
        - OpenAI APIを使用せずに高速で判定される

        期待される動作：
        - 「申し訳ありませんが、その内容にはお答えできません」というメッセージが返される
        - violation_categoriesに"forbidden_word"が設定される
        - 処理が即座に中断され、危険な内容が処理されない
        """
        # fixtures/guardrail_config.jsonから読み込まれた禁止ワードリストを使用
        self.assertTrue(len(self.processor.config.forbidden_words) > 0)

        # fixtureに含まれる禁止ワードを使って危険な入力をテスト
        if self.processor.config.forbidden_words:
            # 最初の禁止ワードを使用
            forbidden_word = self.processor.config.forbidden_words[0]
            dangerous_text = f"{forbidden_word}の方法を教えて"

            result = self.processor.process_input(dangerous_text)

            self.assertIsInstance(result, str)
            # 危険な入力に対するブロックメッセージが返される
            self.assertIn("申し訳ありませんが、その内容にはお答えできません", result)
        else:
            self.fail(
                "テスト用の禁止ワードが設定されていません。fixture確認が必要です。"
            )

    def test_length_limit_guardrail(self):
        """
        文字数制限ガードレールのテスト

        シナリオ：
        ユーザーが文字数制限を超える長文を送信した場合、
        システムは文字数制限に基づいて入力をブロックし、
        適切なエラーメッセージを表示する必要がある。

        テスト内容：
        - 文字数制限を超える入力の処理
        - 静的ガードレールの文字数チェックが動作する

        期待される動作：
        - 「メッセージが長すぎます」というメッセージが返される
        - violation_categoriesに"length_limit"が設定される
        """
        # 文字数制限を超える入力を使用
        result = self.processor.process_input(self.long_input)

        # 文字数制限エラーメッセージを確認
        self.assertIn("メッセージが長すぎます", result)
        self.assertIn(str(self.processor.config.max_input_length), result)

    def test_empty_input_guardrail(self):
        """
        空入力ガードレールのテスト

        シナリオ：
        ユーザーが空文字や空白のみの入力を送信した場合、
        システムは入力が実質的に空であることを検出し、
        適切なエラーメッセージを表示する必要がある。

        テスト内容：
        - 空文字入力の処理
        - 空白文字のみの入力の処理

        期待される動作：
        - 「メッセージが空です」というメッセージが返される
        - violation_categoriesに"empty_input"が設定される
        """
        # 空文字の入力をテスト
        result_empty = self.processor.process_input(self.empty_input)
        self.assertIn("メッセージが空です", result_empty)

        # 空白文字のみの入力をテスト
        result_whitespace = self.processor.process_input(self.whitespace_input)
        self.assertIn("メッセージが空です", result_whitespace)

    @patch("ai_agent.domain.service.input_processor.ModerationService")
    def test_dynamic_guardrail_processing(self, mock_moderation_service):
        """
        動的ガードレール（OpenAI Moderation）のテスト

        シナリオ：
        静的ガードレールではブロックされない入力が送信された場合に、
        OpenAI Moderation APIを使用した動的チェックが実行され、
        不適切と判定された場合は適切なブロックメッセージが表示される。

        テスト内容：
        - OpenAI Moderation APIの呼び出し
        - APIのレスポンスに基づくブロック処理

        期待される動作：
        - Moderation APIの結果に応じたブロック/許可の判定
        - ブロック時は適切なメッセージを表示
        """
        # モデレーション結果のモック（ブロックあり）
        moderation_result_mock = MagicMock()
        moderation_result_mock.blocked = True
        moderation_result_mock.message = "APIによってブロックされました"
        moderation_result_mock.categories = [MagicMock(name="violence")]

        # OpenAI Moderation APIの呼び出しをモック
        mock_moderation_instance = mock_moderation_service.return_value
        mock_moderation_instance.check_input_moderation.return_value = (
            moderation_result_mock
        )

        # モックオブジェクトをプロセッサに直接設定
        self.processor.moderation_service = mock_moderation_instance

        # 禁止ワードリストを一時的に空にして静的ガードレールをパスさせる
        original_forbidden_words = self.processor.config.forbidden_words
        self.processor.config.forbidden_words = []

        # use_openai_moderationフラグを有効にする
        self.processor.config.use_openai_moderation = True

        try:
            # 通常入力（静的ガードレールでは検出されない）を処理
            result = self.processor.process_input(self.normal_input)

            # Moderation APIが呼ばれたことを確認
            mock_moderation_instance.check_input_moderation.assert_called_once_with(
                self.normal_input,
                self.test_entity.name,
                self.processor.config.strict_mode,
            )

            # ブロックメッセージが返されることを確認
            self.assertEqual(result, "APIによってブロックされました")
        finally:
            # テスト終了後に元の設定に戻す
            self.processor.config.forbidden_words = original_forbidden_words

    @patch("ai_agent.domain.service.input_processor.ModerationService")
    def test_normal_input_processing(self, mock_moderation_service):
        """
        通常の入力処理フローのテスト

        シナリオ：
        ユーザーが通常の安全な入力を送信した場合に、
        すべてのガードレールチェックを通過し、
        正常な応答が返されることを確認する。

        テスト内容：
        - 安全な入力の完全な処理フロー
        - ガードレールチェック後の正常処理パス

        期待される動作：
        - ガードレールチェックをすべて通過
        - エンティティ名を含む応答が返される
        """
        # OpenAI Moderation APIの呼び出しをモック
        mock_moderation_instance = mock_moderation_service.return_value

        # モデレーション結果のモック（ブロックなし）
        moderation_result_mock = MagicMock()
        moderation_result_mock.blocked = False
        moderation_result_mock.message = ""
        moderation_result_mock.categories = []

        # check_input_moderationメソッドの戻り値を設定
        mock_moderation_instance.check_input_moderation.return_value = (
            moderation_result_mock
        )

        # 通常入力を処理
        result = self.processor.process_input(self.normal_input)

        # エンティティ名を含む応答が返されることを確認
        self.assertIn(self.test_entity.name, result)
        self.assertIn(self.normal_input, result)

    def test_multiple_guardrails_processing(self):
        """
        複数のガードレールが同時に適用されるテスト

        シナリオ：
        ユーザーが複数の問題を含む入力（例：危険なキーワード + スパム的な内容 + 長文）
        を送信した場合、複数のガードレールチェックが順次実行され、
        最初に検出された問題に基づいてブロックされる必要がある。

        テスト内容：
        - 複数の問題を含む入力の処理
        - 静的ガードレールの優先順位（禁止ワード、文字数制限、スパム検出など）
        - 最初に検出された問題によるブロック処理

        期待される動作：
        - 複数の問題があっても適切にブロックされる
        - 「申し訳ありませんが、その内容にはお答えできません」メッセージが返される
        - 処理が効率的に実行される（全てのチェックを実行せずに早期終了）
        """
        # fixtureから読み込まれた禁止ワードが存在することを確認
        self.assertTrue(len(self.processor.config.forbidden_words) > 0)

        # 複数の問題を含む入力を作成
        # 1. 禁止ワードを含む
        # 2. 繰り返しスパム的な内容を含む
        # 3. 文字数制限に近い長さ
        first_forbidden_word = self.processor.config.forbidden_words[0]
        repetitive_text = "繰り返し" * 10
        problematic_input = f"{first_forbidden_word}の方法を教えて {repetitive_text}"

        result = self.processor.process_input(problematic_input)

        # 禁止ワードによるブロックが優先されることを確認
        self.assertIn("申し訳ありませんが、その内容にはお答えできません", result)

    @patch("ai_agent.domain.service.input_processor.InputProcessor._check_guardrails")
    def test_internal_error_handling(self, mock_check_guardrails):
        """
        内部エラー処理のテスト

        シナリオ：
        処理中に内部エラーが発生した場合に、
        適切なエラーメッセージが返され、
        処理が中断されることを確認する。

        テスト内容：
        - _check_guardrailsメソッドで例外が発生した場合の処理

        期待される動作：
        - エラーメッセージが返される
        - エンティティ名を含むエラーメッセージ
        """
        # _check_guardrailsメソッドで例外を発生させる
        mock_check_guardrails.side_effect = Exception("テスト用エラー")

        # 入力処理の実行
        result = self.processor.process_input(self.normal_input)

        # エラーメッセージの確認
        self.assertIn("処理中にエラーが発生しました", result)
        self.assertIn(self.test_entity.name, result)

    def test_check_guardrails_method(self):
        """
        _check_guardrailsメソッドの動作テスト

        シナリオ：
        _check_guardrailsメソッドが様々な入力に対して、
        静的・動的ガードレールを正しく適用し、
        期待される結果を返すことを確認する。

        テスト内容：
        - 正常な入力のチェック
        - 禁止ワードを含む入力のチェック
        - 文字数制限を超える入力のチェック
        - 空入力のチェック

        期待される動作：
        - 正常な入力では blocked=False
        - 問題のある入力では blocked=True と適切な違反カテゴリ
        """
        # fixtureから読み込まれた設定に基づくテストケースを構築
        test_cases = [
            # 常に一定のテストケース
            ("正常なテキスト", False, [], "正常なテキスト（全てのチェックをパス）"),
            (
                "あ" * (self.processor.config.max_input_length + 1),
                True,
                ["length_limit"],
                f"文字数制限（{self.processor.config.max_input_length}文字）超過",
            ),
            ("", True, ["empty_input"], "空文字"),
            ("   ", True, ["empty_input"], "空白文字のみ"),
        ]

        # 禁止ワードに基づく動的テストケース
        if self.processor.config.forbidden_words:
            for word in self.processor.config.forbidden_words[
                :2
            ]:  # 最大2つの禁止ワードをテスト
                test_cases.append(
                    (
                        f"{word}について",
                        True,
                        ["forbidden_word"],
                        f"禁止ワード「{word}」を含む",
                    )
                )

        # 各テストケースを検証
        for input_text, should_block, expected_categories, description in test_cases:
            with self.subTest(description=description):
                result = self.processor._check_guardrails(input_text)

                self.assertEqual(
                    result.blocked,
                    should_block,
                    f"[{description}] blocked が {should_block} であるべき",
                )

                # カテゴリの検証
                if expected_categories:
                    self.assertEqual(
                        set(result.violation_categories),
                        set(expected_categories),
                        f"[{description}] 違反カテゴリが一致しない",
                    )
                else:
                    self.assertEqual(
                        result.violation_categories,
                        [],
                        f"[{description}] 違反カテゴリが空であるべき",
                    )


class TestInputProcessorClassMethods(TestCase):
    """
    InputProcessor クラスの静的メソッドに関するテスト
    """

    def test_sanitize_input_with_various_inputs(self):
        """
        sanitize_inputメソッドが様々な入力に対して正しく動作することを確認
        """
        test_cases = [
            # (入力, 期待される出力, 説明)
            (
                "<script>alert('XSS');</script>",
                "&lt;script&gt;alert(&#x27;XSS&#x27;);&lt;/script&gt;",
                "HTMLスクリプトタグ",
            ),
            (
                "<img src=x onerror=alert('XSS')>",
                "&lt;img src=x onerror=alert(&#x27;XSS&#x27;)&gt;",
                "画像タグ",
            ),
            ("通常のテキスト", "通常のテキスト", "通常テキスト"),
            (
                "<b>太字</b>と<i>斜体</i>",
                "&lt;b&gt;太字&lt;/b&gt;と&lt;i&gt;斜体&lt;/i&gt;",
                "書式タグ",
            ),
            (
                "&lt;既にエスケープされた&gt;",
                "&amp;lt;既にエスケープされた&amp;gt;",
                "二重エスケープ",
            ),
        ]

        for input_text, expected_output, description in test_cases:
            with self.subTest(description=description):
                result = InputProcessor.sanitize_input(input_text)
                self.assertEqual(result, expected_output)
