import re
import os
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum


class Status(Enum):
    """
    チェック結果のステータスを表す列挙型。
    """

    OK = "OK"
    ERROR = "ERROR"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


@dataclass
class CheckResult:
    """
    個別のチェック項目の実行結果を保持するデータクラス。

    Attributes:
        name (str): チェック項目の名称。
        status (Status): チェック結果のステータス。
        message (str): ユーザー向けのメッセージ。
        details (Dict[str, Any]): 補足情報やデバッグ用の詳細データ。
    """

    name: str
    status: Status
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        """
        結果を辞書形式に変換します。JSON出力などに利用されます。
        """
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


class LLMHealthCheck:
    """
    LLM API (OpenAI, Gemini, Azure OpenAI) の接続状況、環境変数、互換性を
    総合的にチェックするためのクラス。
    """

    def __init__(self):
        """
        LLMHealthCheck を初期化し、空の結果リストを作成します。
        """
        self.results: List[CheckResult] = []

    def add_result(self, result: CheckResult):
        """
        チェック結果をリストに追加します。

        Args:
            result (CheckResult): 追加するチェック結果。
        """
        self.results.append(result)

    def get_summary(self) -> Dict[str, Any]:
        """
        これまでの全チェック結果のサマリーを取得します。

        Returns:
            Dict[str, Any]: 全体のステータスと個別のチェック結果を含む辞書。
        """
        return {
            "overall_status": (
                Status.OK.value
                if all(r.status != Status.ERROR for r in self.results)
                else Status.ERROR.value
            ),
            "checks": [r.to_dict() for r in self.results],
        }

    def check_dependencies(self):
        """
        SDK/依存関係のチェック。
        必要なライブラリ (openai, python-dotenv) がインストールされているか確認します。

        Returns:
            bool: 必須ライブラリが揃っている場合は True、不足している場合は False。
        """
        missing_packages = []
        try:
            import openai
        except ImportError:
            missing_packages.append("openai")

        try:
            import dotenv
        except ImportError:
            missing_packages.append("python-dotenv")

        if missing_packages:
            self.add_result(
                CheckResult(
                    "Dependencies",
                    Status.ERROR,
                    f"Missing packages: {', '.join(missing_packages)}",
                )
            )
            return False
        else:
            self.add_result(
                CheckResult(
                    "Dependencies", Status.OK, "All required packages are installed."
                )
            )
            return True

    def check_environment_variables(self):
        """
        環境変数のチェック。
        APIキーの存在と、正規表現による形式の妥当性を確認します。
        """
        # OpenAI API Key: sk-proj-... (新しい形式) or sk-... (古い形式)
        # 最近は sk-proj- が多い。32文字以上。
        openai_pattern = re.compile(r"^sk-(?:proj-)?[a-zA-Z0-9_-]{32,}$")
        # Gemini API Key: AIza...
        gemini_pattern = re.compile(r"^AIza[a-zA-Z0-9_-]{35}$")
        # Azure OpenAI
        azure_key_pattern = re.compile(r"^[a-f0-9]{32}$")

        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            if openai_pattern.match(openai_key):
                self.add_result(
                    CheckResult("Env: OPENAI_API_KEY", Status.OK, "Format is valid.")
                )
            else:
                self.add_result(
                    CheckResult(
                        "Env: OPENAI_API_KEY",
                        Status.WARNING,
                        "Format might be invalid (should start with sk- and be at least 32 chars).",
                    )
                )
        else:
            self.add_result(
                CheckResult("Env: OPENAI_API_KEY", Status.ERROR, "Not found.")
            )

        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            # GeminiはJSON形式の場合もあるという要件だが、一旦文字列形式をチェック
            if gemini_pattern.match(gemini_key):
                self.add_result(
                    CheckResult("Env: GEMINI_API_KEY", Status.OK, "Format is valid.")
                )
            else:
                # JSON形式かどうかの簡易チェック
                try:
                    json.loads(gemini_key)
                    self.add_result(
                        CheckResult(
                            "Env: GEMINI_API_KEY", Status.OK, "Valid JSON format."
                        )
                    )
                except json.JSONDecodeError:
                    self.add_result(
                        CheckResult(
                            "Env: GEMINI_API_KEY",
                            Status.WARNING,
                            "Format might be invalid (should start with AIza or be valid JSON).",
                        )
                    )
        else:
            self.add_result(
                CheckResult("Env: GEMINI_API_KEY", Status.ERROR, "Not found.")
            )

        azure_open_ai_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_open_ai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if azure_open_ai_key:
            if azure_key_pattern.match(azure_open_ai_key):
                self.add_result(
                    CheckResult(
                        "Env: AZURE_OPENAI_API_KEY", Status.OK, "Format is valid."
                    )
                )
            else:
                self.add_result(
                    CheckResult(
                        "Env: AZURE_OPENAI_API_KEY",
                        Status.WARNING,
                        "Format might be invalid (should be 32 hex chars).",
                    )
                )
        else:
            self.add_result(
                CheckResult("Env: AZURE_OPENAI_API_KEY", Status.ERROR, "Not found.")
            )

        if azure_open_ai_endpoint:
            if (
                azure_open_ai_endpoint.startswith("https://")
                and ".openai.azure.com" in azure_open_ai_endpoint
            ):
                self.add_result(
                    CheckResult(
                        "Env: AZURE_OPENAI_ENDPOINT", Status.OK, "Format is valid."
                    )
                )
            else:
                self.add_result(
                    CheckResult(
                        "Env: AZURE_OPENAI_ENDPOINT",
                        Status.WARNING,
                        "Format might be invalid.",
                    )
                )
        else:
            self.add_result(
                CheckResult("Env: AZURE_OPENAI_ENDPOINT", Status.ERROR, "Not found.")
            )

    def check_endpoints(self):
        """
        エンドポイントの有効性チェック。
        実際に各APIサーバーへリクエストを送り、通信可能か確認します。
        ※課金が発生しない軽量なリクエスト（モデル一覧の取得のみ）を使用しています。
        """
        from openai import OpenAI, AzureOpenAI, APIError

        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                # 注意: client.models.list() は課金が発生しないリクエストです。
                client = OpenAI(api_key=openai_key)
                models = client.models.list()
                model_ids = [m.id for m in models]
                self.add_result(
                    CheckResult(
                        "Endpoint: OpenAI",
                        Status.OK,
                        "Successfully retrieved model list (Billing-safe).",
                        {"model_count": len(model_ids), "sample_models": model_ids[:5]},
                    )
                )
            except APIError as e:
                self.add_result(CheckResult("Endpoint: OpenAI", Status.ERROR, str(e)))
            except Exception as e:
                self.add_result(
                    CheckResult(
                        "Endpoint: OpenAI", Status.ERROR, f"Unexpected error: {e}"
                    )
                )
        else:
            self.add_result(
                CheckResult("Endpoint: OpenAI", Status.SKIPPED, "API Key not provided.")
            )

        # Gemini (OpenAI互換エンドポイント)
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                # 注意: client.models.list() は課金が発生しないリクエストです。
                client = OpenAI(
                    api_key=gemini_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                )
                models = client.models.list()
                model_ids = [m.id for m in models]
                self.add_result(
                    CheckResult(
                        "Endpoint: Gemini",
                        Status.OK,
                        "Successfully retrieved model list (Billing-safe).",
                        {"model_count": len(model_ids), "sample_models": model_ids[:5]},
                    )
                )
            except APIError as e:
                self.add_result(CheckResult("Endpoint: Gemini", Status.ERROR, str(e)))
            except Exception as e:
                self.add_result(
                    CheckResult(
                        "Endpoint: Gemini", Status.ERROR, f"Unexpected error: {e}"
                    )
                )
        else:
            self.add_result(
                CheckResult("Endpoint: Gemini", Status.SKIPPED, "API Key not provided.")
            )

        # Azure OpenAI
        azure_open_ai_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_open_ai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if azure_open_ai_key and azure_open_ai_endpoint:
            try:
                # 注意: client.models.list() は課金が発生しないリクエストです。
                client = AzureOpenAI(
                    api_key=azure_open_ai_key,
                    api_version="2024-02-01",
                    azure_endpoint=azure_open_ai_endpoint,
                )
                # Azureはmodels.list()が使えない場合や権限が必要な場合があるため、
                # ここでは接続確認程度に留めるか、可能ならモデル取得
                client.models.list()
                self.add_result(
                    CheckResult(
                        "Endpoint: AzureOpenAI",
                        Status.OK,
                        "Successfully connected (Billing-safe).",
                    )
                )
            except APIError as e:
                self.add_result(
                    CheckResult("Endpoint: AzureOpenAI", Status.ERROR, str(e))
                )
            except Exception as e:
                self.add_result(
                    CheckResult(
                        "Endpoint: AzureOpenAI", Status.ERROR, f"Unexpected error: {e}"
                    )
                )

    def _check_client_compatibility(
        self,
        name: str,
        api_key: str | None,
        base_url: str | None,
        target_models: List[str],
    ):
        """
        モデルの使用権限および利用可否をチェックする共通ロジック。
        APIキー自体が有効でも、特定のモデル（gpt-4oなど）に対して利用権限がない場合や、
        Azure OpenAIでデプロイされていない場合などを検知します。

        Args:
            name (str): サービス名 (OpenAI, Gemini など)。
            api_key (str | None): APIキー。
            base_url (str | None): ベースURL (Geminiなどの互換エンドポイント用)。
            target_models (List[str]): 使用権限を確認したいモデル名のリスト。
        """
        display_name = f"Model Permission/Availability ({name})"
        if not api_key:
            self.add_result(
                CheckResult(
                    display_name,
                    Status.SKIPPED,
                    "API Key not provided.",
                )
            )
            return

        try:
            from openai import OpenAI, APIError
        except ImportError:
            # check_dependenciesでチェック済みだが念のため
            return

        try:
            client_params = {"api_key": api_key}
            if base_url:
                client_params["base_url"] = base_url
            client = OpenAI(**client_params)

            available_models = [m.id for m in client.models.list()]
            self._evaluate_and_add_model_result(
                available_models, target_models, display_name
            )
        except APIError as e:
            self.add_result(
                CheckResult(
                    display_name,
                    Status.SKIPPED,
                    f"Could not check due to API error: {e}",
                )
            )
        except Exception as e:
            self.add_result(
                CheckResult(
                    display_name,
                    Status.SKIPPED,
                    f"Could not check due to unexpected error: {e}",
                )
            )

    def _check_azure_compatibility(
        self,
        api_key: str | None,
        endpoint: str | None,
        target_models: List[str],
    ):
        """
        Azure OpenAI のモデル利用可否（デプロイ状況）をチェックします。

        Args:
            api_key (str | None): Azure OpenAI APIキー。
            endpoint (str | None): Azure OpenAI エンドポイント。
            target_models (List[str]): 確認したいデプロイ名（モデル名）のリスト。
        """
        display_name = "Model Permission/Availability (AzureOpenAI)"
        if not api_key or not endpoint:
            self.add_result(
                CheckResult(
                    display_name,
                    Status.SKIPPED,
                    "API Key or Endpoint not provided.",
                )
            )
            return

        try:
            from openai import AzureOpenAI, APIError
        except ImportError:
            return

        try:
            client = AzureOpenAI(
                api_key=api_key,
                api_version="2024-02-01",
                azure_endpoint=endpoint,
            )

            # Azureでは models.list() で取得できる ID はデプロイ名に対応する
            available_models = [m.id for m in client.models.list()]
            self._evaluate_and_add_model_result(
                available_models, target_models, display_name
            )
        except APIError as e:
            self.add_result(
                CheckResult(
                    display_name,
                    Status.SKIPPED,
                    f"Could not check due to API error: {e}",
                )
            )
        except Exception as e:
            self.add_result(
                CheckResult(
                    display_name,
                    Status.SKIPPED,
                    f"Could not check due to unexpected error: {e}",
                )
            )

    def _evaluate_and_add_model_result(
        self,
        available_models: List[str],
        target_models: List[str],
        display_name: str,
    ):
        """
        取得したモデルリストと期待するモデルリストを比較し、結果を記録します。

        Args:
            available_models (List[str]): APIから取得した利用可能なモデルIDのリスト。
            target_models (List[str]): チェック対象のモデルIDのリスト。
            display_name (str): チェック項目の表示名。
        """
        found = [m for m in target_models if m in available_models]
        missing = [m for m in target_models if m not in available_models]

        status = Status.OK if found else Status.WARNING
        msg = f"Found: {', '.join(found)}. Missing: {', '.join(missing)}"
        self.add_result(CheckResult(display_name, status, msg))

    def check_model_compatibility(self):
        """
        プロジェクトで使用するモデルが現在のAPIキーで「利用権限」があるか確認します。

        チェックの意義:
        - OpenAI: アカウントのTier制限により最新モデルが使えないケースの検知。
        - Azure OpenAI: 特定のモデルがデプロイ（配置）されていないケースの検知。
        - Gemini: 正しいモデル指定名（接頭辞の有無など）の確認。
        """
        # プロジェクトで使用されている主要なモデルがリストに含まれているか確認
        # lib/llm/valueobject/config.py で定義されているものを基準にする
        target_openai_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "dall-e-3",
        ]
        target_gemini_models = [
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "models/gemini-2.0-flash",
            "models/gemini-2.5-flash",
        ]
        target_azure_models = [
            "gpt-4o",
            "gpt-35-turbo",
        ]

        # OpenAI
        self._check_client_compatibility(
            "OpenAI", os.getenv("OPENAI_API_KEY"), None, target_openai_models
        )

        # Gemini
        self._check_client_compatibility(
            "Gemini",
            os.getenv("GEMINI_API_KEY"),
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            target_gemini_models,
        )

        # Azure OpenAI
        self._check_azure_compatibility(
            os.getenv("AZURE_OPENAI_API_KEY"),
            os.getenv("AZURE_OPENAI_ENDPOINT"),
            target_azure_models,
        )

    def print_formatted_summary(self):
        """
        結果を人間が読みやすい形式で表示する。
        """
        check_summary = self.get_summary()
        status_colors = {
            "OK": "\033[92m[OK]\033[0m",
            "ERROR": "\033[91m[ERROR]\033[0m",
            "WARNING": "\033[93m[WARNING]\033[0m",
            "SKIPPED": "\033[90m[SKIPPED]\033[0m",
        }

        print("\n" + "=" * 70)
        print(" LLM Health Check Summary")
        print(" (Billing-safe: Only metadata/model list retrieval is performed)")
        print("=" * 70)

        overall_status = check_summary["overall_status"]
        color = status_colors.get(overall_status, overall_status)
        print(f"Overall Status: {color}")
        print("-" * 70)

        for check in check_summary["checks"]:
            name = check["name"].ljust(45)
            status = status_colors.get(check["status"], check["status"])
            msg = check["message"]
            print(f"{name} {status} {msg}")

        print("=" * 70 + "\n")

    def run_all(self, print_summary=False):
        """
        すべてのチェック項目（依存関係、環境変数、エンドポイント、互換性）を順番に実行します。

        Args:
            print_summary (bool): 結果をコンソールに表示するかどうか。

        Returns:
            Dict[str, Any]: 全体のチェック結果サマリー。
        """
        if self.check_dependencies():
            self.check_environment_variables()
            self.check_endpoints()
            self.check_model_compatibility()

        if print_summary:
            self.print_formatted_summary()

        return self.get_summary()


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    # デフォルトの.envパスをスクリプトの場所基準で解決する
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # lib/llm/prototype/llm_health_check.py -> lib/llm/.env
    default_env_path = os.path.join(script_dir, "..", ".env")

    parser = argparse.ArgumentParser(description="LLM Health Check")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    parser.add_argument(
        "--env", type=str, default=default_env_path, help="Path to .env file"
    )
    args = parser.parse_args()

    # .envを読み込む
    if os.path.exists(args.env):
        load_dotenv(args.env)

    checker = LLMHealthCheck()
    summary = checker.run_all(print_summary=not args.json)

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
