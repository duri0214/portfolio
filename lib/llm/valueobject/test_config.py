from unittest import TestCase

from lib.llm.valueobject.config import (
    LlmModelProfile,
    ModelDefaults,
    ModelName,
    OpenAIGptConfig,
)


class ModelConfigTest(TestCase):
    def test_gpt_5_6_model_names_are_available(self):
        """
        シナリオ:
        - 入力: 共通モデル名値オブジェクト。
        - 処理: GPT-5.6系の3モデル名を参照する。
        - 期待値: OpenAI APIへ渡す正式なモデルIDが取得できる。
        """
        self.assertEqual(ModelName.GPT_5_6_SOL, "gpt-5.6-sol")
        self.assertEqual(ModelName.GPT_5_6_TERRA, "gpt-5.6-terra")
        self.assertEqual(ModelName.GPT_5_6_LUNA, "gpt-5.6-luna")
        self.assertEqual(ModelName.GPT_5_6, "gpt-5.6")

    def test_defaults_keep_model_selection_per_use_case(self):
        """
        シナリオ:
        - 入力: 本番用途別の共通モデルプロファイル。
        - 処理: Kokkai、通常チャット、Agentの既定値を比較する。
        - 期待値: 全用途を単一モデルへ寄せず、API種別とstructured outputs対応も確認できる。
        """
        self.assertIsInstance(ModelDefaults.KOKKAI_SCENARIO, LlmModelProfile)
        self.assertEqual(ModelDefaults.KOKKAI_SCENARIO.model, ModelName.GPT_5_6_LUNA)
        self.assertEqual(ModelDefaults.LLM_CHAT.model, ModelName.GPT_5_6_TERRA)
        self.assertEqual(ModelDefaults.AI_AGENT.model, ModelName.GPT_5_6_SOL)
        self.assertEqual(ModelDefaults.AI_AGENT.api, "responses")
        self.assertTrue(ModelDefaults.KOKKAI_SCENARIO.supports_structured_outputs)

    def test_openai_config_is_built_from_chat_completions_profile(self):
        """
        シナリオ:
        - 入力: Kokkai向けの共通モデルプロファイルとAPI接続情報。
        - 処理: OpenAIGptConfig.from_profileでChat Completions設定を生成する。
        - 期待値: モデルID、推論量、APIキー、最大トークン数が設定へ引き継がれる。
        """
        config = OpenAIGptConfig.from_profile(
            ModelDefaults.KOKKAI_SCENARIO,
            api_key="test-key",
            max_tokens=4000,
        )

        self.assertEqual(config.model, ModelName.GPT_5_6_LUNA)
        self.assertEqual(config.reasoning_effort, "low")
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.max_tokens, 4000)

    def test_openai_config_rejects_responses_profile(self):
        """
        シナリオ:
        - 入力: Responses APIを選択したAgent向けプロファイル。
        - 処理: Chat Completions専用Configの生成を試みる。
        - 期待値: API経路の取り違えをValueErrorで検知する。
        """
        with self.assertRaisesRegex(ValueError, "Chat Completions profile"):
            OpenAIGptConfig.from_profile(
                ModelDefaults.AI_AGENT,
                api_key="test-key",
                max_tokens=100,
            )
