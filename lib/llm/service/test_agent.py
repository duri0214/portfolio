from unittest.mock import Mock, patch

from django.test import TestCase

from lib.llm.service.agent import ModerationService


def create_mock_safe_response(text: str = "こんにちは、お元気ですか？") -> Mock:
    """
    OpenAI Moderation API の「安全なレスポンス」を模倣したモックオブジェクトを生成する。

    この関数は、flagged=False（安全）かつすべてのカテゴリが False の
    モデレーション結果を返すように設定されたモックを返します。

    主にユニットテストにおいて、正常系（safe content）のシナリオを再現するために使用します。

    Args:
        text (str): モックレスポンスに含める入力テキスト（任意、デフォルトは日本語の挨拶）

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


def create_mock_unsafe_response(text: str = "暴力的な内容を含むテキスト") -> Mock:
    """
    OpenAI Moderation API の「不適切なレスポンス（flagged=True）」を模倣したモックオブジェクトを生成する。

    この関数は、flagged=True（危険）かつ "violence" カテゴリのみ True の
    モデレーション結果を返すように設定されたモックを返します。

    主にユニットテストにおいて、異常系（unsafe content）のシナリオを再現するために使用します。

    Args:
        text (str): モックレスポンスに含める入力テキスト（任意、デフォルトは不適切な日本語の例）

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
        - message は API のフィールドではなく、アプリケーションレベルの通知文言として扱う

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

        self.mock_safe_response = create_mock_safe_response(self.safe_text)
        self.mock_unsafe_response = create_mock_unsafe_response(self.unsafe_text)

    def test_check_input_moderation_safe_content(self):
        """
        [正常系] ユーザー入力が安全な場合のモデレーション動作を検証する

        シナリオ:
            - OpenAI Moderation API に安全な入力テキストを渡す
            - APIレスポンスは `flagged=False`（違反なし）を返す
            - サービスは blocked=False, message="" を返却する

        期待される結果:
            - `blocked` は False
            - `message` は空文字列
            - `categories` に違反カテゴリが含まれない

        重要度:
            高 — 通常利用時の想定パスであり、誤ブロックがないことを確認する
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
        [異常系] ユーザー入力が危険なコンテンツの場合の検出処理を検証する

        シナリオ:
            - 不適切な入力テキストを与える
            - API は `flagged=True` および `violence=True` を含むレスポンスを返す
            - サービスは blocked=True, エラーメッセージ, 違反カテゴリを返す

        期待される結果:
            - `blocked` は True
            - `message` にブロック理由とエンティティ名が含まれる
            - `categories` に "violence" を含む

        重要度:
            高 — ユーザー保護・規約遵守のために確実に検出されることが必要
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
        [エラー系] API失敗時に strict_mode=False の場合の寛容な処理を検証する

        シナリオ:
            - Moderation API から例外が発生
            - strict_mode=False（非厳格モード）で呼び出す
            - サービスはエラーログを出力しつつ blocked=False で処理を許可

        期待される結果:
            - `blocked` は False
            - `message` は空文字列
            - エラー内容がロガーに出力される

        重要度:
            中 — 一時的なAPI障害がユーザー体験に過度な影響を与えないことを保証
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
        [エラー系] API失敗時に strict_mode=True の場合、安全側に倒す処理を検証する

        シナリオ:
            - Moderation API から例外が発生
            - strict_mode=True（厳格モード）で呼び出す
            - サービスは blocked=True を返却し、利用不可メッセージを返す

        期待される結果:
            - `blocked` は True
            - `message` に「安全性チェックが利用できません」が含まれる

        重要度:
            高 — 安全重視運用モードにおいてリスク排除を優先する設計
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
            - 安全な出力テキストを与える
            - APIは `flagged=False` を返す
            - サービスはそのままの出力を返却する

        期待される結果:
            - `blocked` は False
            - `message` は空文字列（= ブロックなし）

        重要度:
            高 — 通常の応答が正しく処理されることを保証
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
        [異常系] AI出力が不適切なコンテンツの場合の検出処理を検証する

        シナリオ:
            - 危険な出力テキストを与える
            - APIは `flagged=True` を返す
            - サービスは代替の警告メッセージを返す

        期待される結果:
            - `blocked` は True
            - `message` に「適切な回答を生成できませんでした」などの文言が含まれる
            - エンティティ名も含まれる

        重要度:
            高 — ユーザーへの不適切な出力を確実に防止する
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
        入力ガードレール関数の生成とその動作確認

        シナリオ:
            - `create_moderation_guardrail` を使って関数を生成
            - その関数が適切にモデレーションを呼び出すか検証

        期待される結果:
            - 呼び出し可能な関数が返る
            - unsafe_text を与えると `blocked=True` を返す

        重要度:
            中 — Agents SDK との接続点として正しく機能することが必要
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
        出力ガードレール関数の生成とその動作確認

        シナリオ:
            - `create_output_moderation_guardrail` を使って関数を生成
            - その関数が適切に出力のモデレーションを行うか確認

        期待される結果:
            - 呼び出し可能な関数が返る
            - 危険な出力に対して `blocked=True` を返す

        重要度:
            中 — 応答内容のフィルタリング機構として正しく動作することが重要
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
        ModerationService の初期化が正常に行われるかを確認する

        シナリオ:
            - インスタンス化時に openai_client が自動的に初期化されているか確認

        期待される結果:
            - service インスタンスが None でないこと
            - `openai_client` プロパティが設定されていること

        重要度:
            低 — 初期化ロジックが壊れていないことを保証
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

        # モッククライアントの作成と差し替え
        self.mock_client = Mock()
        self.service.openai_client = self.mock_client

        self.mock_safe_response = create_mock_safe_response()
        self.mock_unsafe_response = create_mock_unsafe_response()

    def test_full_moderation_workflow(self):
        """
        [統合正常系] 入力と出力モデレーションが連携して機能するかを確認する

        シナリオ:
            1. ユーザーからの入力に対して check_input_moderation を呼び出す
            2. その応答を前提に、check_output_moderation を呼び出す
            3. どちらも安全なケースとして mock safe response を返す

        期待される結果:
            - 両方のモデレーションが blocked=False を返す
            - API呼び出しが2回行われる（入力・出力それぞれ）
            - 正常な会話フローが構築可能

        重要度:
            高 — 入力と出力を通じてサービス全体が連携し、予期通りの動作をするかを保証
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
