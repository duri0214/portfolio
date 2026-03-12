import re
import os
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum
from openai import OpenAI, AzureOpenAI, APIError


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

    def to_dict(self) -> Dict[str, Any]:
        """
        結果を辞書形式に変換します。JSON出力やサマリー作成に利用されます。

        Returns:
            Dict[str, Any]: チェック結果の各属性を含む辞書。
        """
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


class BaseValidator:
    """
    バリデーションクラスの共通基底クラス。
    """

    def __init__(self, owner: "LLMHealthCheck"):
        self.owner = owner

    def validate_all(self):
        """
        すべての対象項目を一括でバリデーションします。
        子クラスで実装される必要があります。
        """
        raise NotImplementedError

    @staticmethod
    def get_client(
        name: str,
        api_key: str | None,
        base_url: str | None = None,
        azure_endpoint: str | None = None,
    ) -> OpenAI | AzureOpenAI | None:
        """
        指定されたプロバイダー名とパラメータに基づいて、OpenAI互換クライアントを初期化します。

        Args:
            name (str): プロバイダーの識別名 ("OpenAI", "Gemini", "AzureOpenAI")。
            api_key (str | None): 使用するAPIキー。Noneの場合はNoneを返します。
            base_url (str | None): カスタムベースURL（GeminiのOpenAI互換API用など）。
            azure_endpoint (str | None): Azure OpenAIのエンドポイントURL。

        Returns:
            OpenAI | AzureOpenAI | None: 初期化されたクライアントインスタンス、またはパラメータ不足時はNone。
        """
        if not api_key:
            return None

        if name == "AzureOpenAI":
            if not azure_endpoint:
                return None
            return AzureOpenAI(
                api_key=api_key,
                api_version="2024-02-01",
                azure_endpoint=azure_endpoint,
            )

        client_params = {"api_key": api_key}
        if base_url:
            client_params["base_url"] = base_url
        return OpenAI(**client_params)


class EnvValidator(BaseValidator):
    """
    環境変数の存在と形式をチェックするためのクラス。
    """

    def _validate(
        self,
        name: str,
        value: str | None,
        pattern: re.Pattern | None = None,
        error_msg: str = "Not found.",
        warning_msg: str = "Format might be invalid.",
    ):
        """
        環境変数の存在確認と形式チェックを行い、結果をオーナーの結果リストに追加します。
        """
        if value:
            if pattern is None or pattern.match(value):
                self.owner.add_result(
                    CheckResult(f"Env: {name}", Status.OK, "Format is valid.")
                )
            else:
                self.owner.add_result(
                    CheckResult(f"Env: {name}", Status.WARNING, warning_msg)
                )
        else:
            self.owner.add_result(CheckResult(f"Env: {name}", Status.ERROR, error_msg))

    def validate_all(self):
        """
        すべての対象環境変数を一括でバリデーションします。
        """
        # OpenAI API Key: sk-proj-... (新しい形式) or sk-... (古い形式)
        openai_pattern = re.compile(r"^sk-(?:proj-)?[a-zA-Z0-9_-]{32,}$")
        # Gemini API Key: AIza...
        gemini_pattern = re.compile(r"^AIza[a-zA-Z0-9_-]{35}$")
        # Azure OpenAI
        azure_key_pattern = re.compile(r"^[a-f0-9]{32}$")

        self._validate(
            "OPENAI_API_KEY",
            os.getenv("OPENAI_API_KEY"),
            openai_pattern,
            warning_msg="Format might be invalid (should start with sk- and be at least 32 chars).",
        )

        self._validate(
            "GEMINI_API_KEY",
            os.getenv("GEMINI_API_KEY"),
            gemini_pattern,
            warning_msg="Format might be invalid (should start with AIza and be at least 39 chars).",
        )

        self._validate(
            "AZURE_OPENAI_API_KEY",
            os.getenv("AZURE_OPENAI_API_KEY"),
            azure_key_pattern,
            warning_msg="Format might be invalid (should be 32 hex chars).",
        )

        azure_open_ai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if azure_open_ai_endpoint:
            if (
                azure_open_ai_endpoint.startswith("https://")
                and ".openai.azure.com" in azure_open_ai_endpoint
            ):
                self.owner.add_result(
                    CheckResult(
                        "Env: AZURE_OPENAI_ENDPOINT", Status.OK, "Format is valid."
                    )
                )
            else:
                self.owner.add_result(
                    CheckResult(
                        "Env: AZURE_OPENAI_ENDPOINT",
                        Status.WARNING,
                        "Format might be invalid.",
                    )
                )
        else:
            self.owner.add_result(
                CheckResult("Env: AZURE_OPENAI_ENDPOINT", Status.ERROR, "Not found.")
            )


class EndpointValidator(BaseValidator):
    """
    LLM API エンドポイントへの接続性をチェックするためのクラス。
    """

    def _validate(
        self,
        name: str,
        client: OpenAI | AzureOpenAI | None,
        skip_msg: str = "API Key not provided.",
    ):
        """
        指定されたクライアントを使用してエンドポイントの接続確認を行います。
        """
        display_name = f"Endpoint: {name}"
        if not client:
            self.owner.add_result(CheckResult(display_name, Status.SKIPPED, skip_msg))
            return

        try:
            models = client.models.list()
            model_ids = [m.id for m in models]
            details = (
                {"model_count": len(model_ids), "sample_models": model_ids[:5]}
                if name != "AzureOpenAI"
                else {}
            )
            msg = (
                "Successfully retrieved model list (Billing-safe)."
                if name != "AzureOpenAI"
                else "Successfully connected (Billing-safe)."
            )
            self.owner.add_result(CheckResult(display_name, Status.OK, msg, details))
        except APIError as e:
            self.owner.add_result(CheckResult(display_name, Status.ERROR, str(e)))
        except Exception as e:
            self.owner.add_result(
                CheckResult(display_name, Status.ERROR, f"Unexpected error: {e}")
            )

    def validate_all(self):
        """
        すべての対象エンドポイントを一括でバリデーションします。
        """
        # OpenAI
        self._validate("OpenAI", self.get_client("OpenAI", os.getenv("OPENAI_API_KEY")))

        # Gemini
        self._validate(
            "Gemini",
            self.get_client(
                "Gemini",
                os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
        )

        # Azure OpenAI
        self._validate(
            "AzureOpenAI",
            self.get_client(
                "AzureOpenAI",
                os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            ),
            skip_msg="API Key or Endpoint not provided.",
        )


class AvailabilityValidator(BaseValidator):
    """
    LLM モデルの利用可能性（権限）をチェックするためのクラス。
    """

    def _validate(
        self,
        name: str,
        client: OpenAI | AzureOpenAI | None,
        target_models: List[str],
        skip_msg: str = "API Key not provided.",
    ):
        """
        特定のプロバイダーにおいて、プロジェクトが要求するモデルが利用可能かどうかをチェックします。
        """
        display_name = f"Model Permission/Availability ({name})"
        if not client:
            self.owner.add_result(CheckResult(display_name, Status.SKIPPED, skip_msg))
            return

        try:
            available_models = [m.id for m in client.models.list()]
            found = [m for m in target_models if m in available_models]
            missing = [m for m in target_models if m not in available_models]

            status = Status.OK if found else Status.WARNING
            msg = f"Found: {', '.join(found)}. Missing: {', '.join(missing)}"
            self.owner.add_result(CheckResult(display_name, status, msg))
        except APIError as e:
            self.owner.add_result(
                CheckResult(
                    display_name,
                    Status.SKIPPED,
                    f"Could not check due to API error: {e}",
                )
            )
        except Exception as e:
            self.owner.add_result(
                CheckResult(
                    display_name,
                    Status.SKIPPED,
                    f"Could not check due to unexpected error: {e}",
                )
            )

    def validate_all(self):
        """
        すべての対象モデルの利用可能性を一括でバリデーションします。
        """
        # OpenAI
        self._validate(
            "OpenAI",
            self.get_client("OpenAI", os.getenv("OPENAI_API_KEY")),
            ["gpt-4o", "gpt-4o-mini", "dall-e-3"],
        )

        # Gemini
        self._validate(
            "Gemini",
            self.get_client(
                "Gemini",
                os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
            [
                "gemini-2.0-flash",
                "gemini-2.5-flash",
                "models/gemini-2.0-flash",
                "models/gemini-2.5-flash",
            ],
        )

        # Azure OpenAI
        self._validate(
            "AzureOpenAI",
            self.get_client(
                "AzureOpenAI",
                os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            ),
            ["gpt-4o", "gpt-35-turbo"],
            skip_msg="API Key or Endpoint not provided.",
        )


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
        self._env_validator = EnvValidator(self)
        self._endpoint_validator = EndpointValidator(self)
        self._availability_validator = AvailabilityValidator(self)

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

    def print_formatted_summary(self):
        """
        これまでの全チェック結果を、色付きの表形式でコンソールに表示します。
        各行には項目名、ステータス([OK], [ERROR], etc.)、および詳細メッセージが含まれます。
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
        すべてのチェック項目（環境変数、エンドポイント、互換性）を順番に実行します。

        Args:
            print_summary (bool): 結果をコンソールに表示するかどうか。

        Returns:
            Dict[str, Any]: 全体のチェック結果サマリー。
        """
        self._env_validator.validate_all()
        self._endpoint_validator.validate_all()
        self._availability_validator.validate_all()

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
