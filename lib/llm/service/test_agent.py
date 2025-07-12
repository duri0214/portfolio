from unittest.mock import Mock, patch

from django.test import TestCase

from lib.llm.service.agent import ModerationService


def create_mock_safe_response() -> Mock:
    """
    OpenAI Moderation API の「安全なレスポンス」を模倣したモックオブジェクトを生成する。

    この関数は、flagged=False（安全）かつすべてのカテゴリが False の
    モデレーション結果を返すように設定されたモックを返します。

    主にユニットテストにおいて、正常系（safe content）のシナリオを再現するために使用します。

    Returns:
        Mock: OpenAI Moderation API のレスポンス形式を模倣したモックオブジェクト

    参考:
        OpenAI Moderation API リファレンス:
        https://platform.openai.com/docs/guides/moderation/overview
    """
    mock_response = Mock()
    result = Mock()
    result.flagged = False
    result.categories.model_dump.return_value = {
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
    mock_response.results = [result]
    return mock_response


def create_mock_unsafe_response() -> Mock:
    """
    OpenAI Moderation API の「不適切なレスポンス（flagged=True）」を模倣したモックオブジェクトを生成する。

    この関数は、flagged=True（危険）かつ "violence" カテゴリのみ True の
    モデレーション結果を返すように設定されたモックを返します。

    主にユニットテストにおいて、異常系（unsafe content）のシナリオを再現するために使用します。

    Returns:
        Mock: OpenAI Moderation API のレスポンス形式を模倣したモックオブジェクト

    参考:
        OpenAI Moderation API リファレンス:
        https://platform.openai.com/docs/guides/moderation/overview
    """
    mock_response = Mock()
    result = Mock()
    result.flagged = True
    result.categories.model_dump.return_value = {
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
    mock_response.results = [result]
    return mock_response


class TestModerationService(TestCase):
    """
    ModerationService クラスのユニットテスト。

    本クラスでは、OpenAI Moderation API のモックレスポンスを用いて、
    コンテンツの安全性評価に関する各種機能を検証する。

    テスト対象のメソッド:
        - check_input_moderation: ユーザー入力に対するモデレーションチェック
        - check_output_moderation: AI出力に対するモデレーションチェック
        - create_moderation_guardrail: 入力モデレーション用ガードレール関数の生成
        - create_output_moderation_guardrail: 出力モデレーション用ガードレール関数の生成

    主な検証観点:
        1. 正常系テスト:
            - 安全なテキストに対して blocked=False を返すか
            - categories が空であるか
        2. 異常系テスト:
            - 危険なテキストに対して blocked=True と適切なメッセージ・カテゴリを返すか
        3. エラー系テスト:
            - OpenAI APIが例外を返した際に、非厳格モードでは許可されるか
            - 厳格モードでは安全側（blocked=True）に倒れるか
        4. ガードレール関数の動作検証:
            - callable であること
            - 内部で適切に ModerationService が使われていること

    テスト設計上の特徴:
        - OpenAI Moderation API の仕様に従ったレスポンスモックを関数で共通化
        - モデレーション結果は VO (ModerationResult) で表現

    参考: OpenAI Moderation API 仕様
    https://platform.openai.com/docs/guides/moderation
    """

    def setUp(self):
        self.service = ModerationService()
        self.entity_name = "テストエンティティ"
        self.safe_text = "こんにちは、お元気ですか？"
        self.unsafe_text = "暴力的な内容を含むテキスト"

        # モッククライアント生成
        self.mock_client = Mock()
        self.service.openai_client = self.mock_client

        self.mock_safe_response = create_mock_safe_response()
        self.mock_unsafe_response = create_mock_unsafe_response()

    def test_check_input_moderation_safe_content(self):
        """
        [正常系] ユーザー入力が安全な場合のモデレーション動作を検証する

        シナリオ:
            - OpenAI Moderation API に安全なテキストを渡す
            - APIは `flagged=False`（違反なし）を返す
            - サービスは `blocked=False`、かつ `message=""`（エラーメッセージなし）を返す

        期待結果:
            - `blocked` は False（処理がブロックされない）
            - `message` は空文字列（エラーなし＝安全な状態）
            - `categories` に違反カテゴリが含まれない

        重要度:
            高 — 通常利用時の想定パスで誤ブロックがないことを確認
        """
        # モックレスポンスを使って統一
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
        [異常系] 不適切なユーザー入力に対する検出処理を検証する

        シナリオ:
            - 不適切なテキストを入力
            - APIは `flagged=True`、かつ違反カテゴリ（例: violence）を返す
            - サービスは `blocked=True`、理由を含むメッセージ、違反カテゴリを返す

        期待結果:
            - `blocked` は True（処理をブロック）
            - `message` にブロック理由とエンティティ名を含む
            - `categories` に該当する違反カテゴリが含まれる

        重要度:
            高 — ユーザー保護・規約遵守のため、確実な検出が必須
        """
        # モックレスポンスを使って統一
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
        [エラー系] API例外発生時、strict_mode=Falseでの寛容な処理を検証する

        シナリオ:
            - Moderation API が例外を発生
            - strict_mode=False で呼び出す
            - サービスはログに警告を出しつつ `blocked=False` で処理を許可

        期待結果:
            - `blocked` は False（処理は許可）
            - `message` は空文字列（エラー表示なし）
            - ログにエラー情報が出力される

        重要度:
            中 — 一時的API障害がユーザー体験を過度に悪化させない設計
        """
        # モックでAPI例外を発生させる
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
        [エラー系] API例外発生時、strict_mode=Trueで安全側に倒す処理を検証する

        シナリオ:
            - Moderation API が例外を発生
            - strict_mode=True で呼び出す
            - サービスは `blocked=True`、安全性チェック不能のメッセージを返す

        期待結果:
            - `blocked` は True（処理をブロック）
            - `message` に安全性チェック不可の旨とエンティティ名を含む

        重要度:
            高 — 安全最優先の運用モードでリスク排除を保証
        """
        # モックでAPI例外を発生させる
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
        [正常系] AI出力が安全な場合のモデレーション処理を検証する

        シナリオ:
            - 安全な出力テキストを入力
            - APIは `flagged=False` を返す
            - サービスは `blocked=False`、空メッセージを返す

        期待結果:
            - `blocked` は False（処理がブロックされない）
            - `message` は空文字列（エラーなし）

        重要度:
            高 — 通常の応答が正常に処理されることを保証
        """
        # モックレスポンスを使って統一
        self.mock_client.moderations.create.return_value = self.mock_safe_response

        # テスト実行
        result = self.service.check_output_moderation(self.safe_text, self.entity_name)

        # 結果検証
        self.assertFalse(result.blocked)
        self.assertEqual(result.message, "")

    def test_check_output_moderation_unsafe_content(self):
        """
        [異常系] AI出力が不適切なコンテンツの場合の検出を検証する

        シナリオ:
            - 危険な出力テキストを入力
            - APIは `flagged=True` を返す
            - サービスは `blocked=True`、警告メッセージを返す

        期待結果:
            - `blocked` は True（出力をブロック）
            - `message` に警告文言とエンティティ名を含む

        重要度:
            高 — 不適切な応答防止のため必須
        """
        # モックレスポンスを使って統一
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
        入力モデレーション用ガードレール関数の生成と動作確認を行う

        シナリオ:
            - `create_moderation_guardrail` で関数生成
            - 生成関数がモデレーションを呼び出し、正しくブロック判定を返すか検証

        期待結果:
            - 呼び出し可能な関数が返る
            - 不適切テキストで `blocked=True` を返す

        重要度:
            中 — Agents SDK 連携の接続点として正確な動作が必要
        """
        # モックレスポンスを使って統一
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
        出力モデレーション用ガードレール関数の生成と動作検証を行う

        シナリオ:
            - `create_output_moderation_guardrail` で関数生成
            - 生成関数が出力のモデレーションを行い適切にブロック判定するか検証

        期待結果:
            - 呼び出し可能な関数が返る
            - 不適切出力で `blocked=True` を返す

        重要度:
            中 — 応答内容のフィルタリング機構として必須
        """
        # モックレスポンスを使って統一
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
        ModerationService の初期化処理を検証する

        シナリオ:
            - インスタンス化時に openai_client が正しく初期化されているか確認

        期待結果:
            - インスタンスが None でないこと
            - `openai_client` がセットされていること

        重要度:
            低 — 初期化ロジックが破綻していないことを保証
        """
        service = ModerationService()
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.openai_client)


class TestModerationServiceIntegration(TestCase):
    """
    ModerationService の統合テストケース

    概要:
        - このクラスでは、ModerationService の複数メソッドを連携させた「統合的な動作確認」を行う。
        - 実運用に近いフローでモデレーションチェックが一貫して正しく行われることを保証する。

    特徴:
        - 入力および出力モデレーション両方の呼び出しを含むテスト
        - API レイヤを含むが、すべてモックによって再現

    注意:
        - OpenAI Moderation API の実際のエンドポイントは呼び出さない（完全モック）
        - 安全なテキストのみを用いて、システムが「正常時にブロックしないこと」を保証する

    参考:
        - OpenAI Moderation API 仕様: https://platform.openai.com/docs/guides/moderation
    """

    def setUp(self):
        """統合テスト用のセットアップ"""
        self.service = ModerationService()
        self.entity_name = "統合テスト用エンティティ"

        # モッククライアント生成
        self.mock_client = Mock()
        self.service.openai_client = self.mock_client

        self.mock_safe_response = create_mock_safe_response()
        self.mock_unsafe_response = create_mock_unsafe_response()

    def test_full_moderation_workflow(self):
        """
        [統合正常系] 入力・出力モデレーションが連携して正常動作するかを検証する

        シナリオ:
            1. 安全なユーザー入力に対して `check_input_moderation` を呼ぶ
            2. 安全なAI出力に対して `check_output_moderation` を呼ぶ
            3. 両方のAPI呼び出しはモックで安全レスポンスを返す

        期待結果:
            - 両方のチェックで `blocked=False` が返る
            - モックAPIの呼び出しがそれぞれ1回ずつ行われる

        重要度:
            高 — 入力・出力両面で正常なサービス連携を保証
        """
        # モックレスポンスを使って統一
        self.mock_client.moderations.create.return_value = create_mock_safe_response()

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
