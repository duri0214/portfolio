import json
import os
from typing import Generator

from django.contrib.auth.models import User
from django.http import StreamingHttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView
from dotenv import load_dotenv

from lib.llm.valueobject.completion import StreamResponse
from llm_chat.domain.repository.chat import ChatLogRepository
from llm_chat.domain.service.chat import (
    RIDDLE_END_MESSAGE,
)
from llm_chat.domain.usecase.chat import (
    UseCase,
    LlmChatUseCase,
    RiddleUseCase,
    OpenAIGptStreamingUseCase,
    OpenAIDalleUseCase,
    OpenAITextToSpeechUseCase,
    OpenAISpeechToTextUseCase,
    OpenAIRagUseCase,
)
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig, ModelName
from llm_chat.forms import UserTextForm
from llm_chat.models import ChatLogs

# .env ファイルを読み込む
load_dotenv()


class IndexView(FormView):
    template_name = "llm_chat/index.html"
    form_class = UserTextForm
    success_url = reverse_lazy("llm:index")

    def get_initial(self):
        """
        フォームの初期値を設定します。

        以下の優先順位で `model_mode` を決定します：
        1. なぞなぞが進行中の場合（最新のなぞなぞ履歴が未終了）："Riddle"
        2. 過去のチャット履歴がある場合：最新のメッセージで使用されたモデル/モード
        3. 履歴がない場合：デフォルトの "OpenAIGpt"
        """
        initial = super().get_initial()
        login_user = self._get_login_user()
        chat_history = ChatLogRepository.find_chat_history(user=login_user)

        # 1. なぞなぞが進行中の場合は、Riddleモードを優先
        if self._is_riddle_active(chat_history):
            initial["model_mode"] = "Riddle"
            return initial

        last_log = chat_history[-1] if chat_history else None

        if last_log:
            # 2. 直近の model_name をそのまま初期値として採用
            # Riddle は _is_riddle_active で判定済みのため、
            # 終了している場合は Riddle 以外のデフォルトに戻す必要があるが、
            # 履歴をクリアしない限り "Riddle" が入っている場合は 1 で return されるか、
            # 終了していればここに来る。終了している場合は OpenAI に戻す。
            if last_log.model_name == "Riddle":
                initial["model_mode"] = "OpenAIGpt"
            else:
                initial["model_mode"] = last_log.model_name or "OpenAIGpt"
        else:
            initial["model_mode"] = "OpenAIGpt"

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        login_user = self._get_login_user()
        chat_history = ChatLogRepository.find_chat_history(user=login_user)

        # JSON フォーマットデータをテンプレートに渡す
        context["chat_history"] = [log.to_display() for log in chat_history]
        context["is_superuser"] = self.request.user.is_superuser
        context["is_riddle_active"] = self._is_riddle_active(chat_history)

        return context

    def _get_login_user(self):
        """ログインユーザーまたはデフォルトユーザー（pk=1）を取得します。"""
        return (
            self.request.user
            if self.request.user.is_authenticated
            else User.objects.get(pk=1)
        )

    @staticmethod
    def _is_riddle_active(chat_history):
        """なぞなぞが進行中か判定します（最新の履歴がなぞなぞで未終了か）。"""
        if not chat_history:
            return False

        last_log = chat_history[-1]
        return last_log.is_riddle and RIDDLE_END_MESSAGE not in (last_log.content or "")


class SyncResponseView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        try:
            use_case_type = request.POST.get("use_case_type")
            user_input = request.POST.get("user_input")
            audio_file = request.FILES.get("audio_file")

            if not use_case_type:
                return JsonResponse({"error": "No use case type provided"}, status=400)

            # 使用するユースケースを切り替え TODO: Use-caseのFactoryにしたらよさそう issue229
            use_case: UseCase | None = None
            if use_case_type in ("Gemini", "OpenAIGpt"):
                # TODO: user_inputでそれぞれのUse-caseを初期化したほうがよさそう issue228
                if use_case_type == "Gemini":
                    config = GeminiConfig(
                        api_key=os.getenv("GEMINI_API_KEY"),
                        max_tokens=4000,
                        model=ModelName.GEMINI_2_5_FLASH,
                    )
                else:
                    config = OpenAIGptConfig(
                        api_key=os.getenv("OPENAI_API_KEY"),
                        max_tokens=4000,
                        model=ModelName.GPT_5_MINI,
                    )
                use_case = LlmChatUseCase(config)
            elif use_case_type == "OpenAIDalle":
                use_case = OpenAIDalleUseCase()
            elif use_case_type == "OpenAITextToSpeech":
                use_case = OpenAITextToSpeechUseCase()
            elif use_case_type == "OpenAISpeechToText":
                if not audio_file:
                    return JsonResponse({"error": "Audio file is required"}, status=400)
                user_input = "N/A"
                use_case = OpenAISpeechToTextUseCase(audio_file=audio_file)
            elif use_case_type == "OpenAIRag":
                use_case = OpenAIRagUseCase()
            elif use_case_type == "Riddle":
                # RiddleはデフォルトでOpenAIを使用（必要に応じてGeminiに変更可）
                config = OpenAIGptConfig(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    max_tokens=4000,
                    model=ModelName.GPT_5_MINI,
                )
                use_case = RiddleUseCase(config)

            if not use_case:
                return JsonResponse(
                    {"error": "Invalid use case type provided"}, status=400
                )

            # ユースケースの実行
            message = use_case.execute(user=request.user, content=user_input)

            # 成功レスポンスを返す
            return JsonResponse(
                {
                    "status": "success",
                    "message": f"{use_case_type} 処理が完了しました",
                    "result": message.to_display(),
                }
            )

        except Exception as e:
            import traceback
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"SyncResponseView Error: {str(e)}")
            logger.error(traceback.format_exc())
            return JsonResponse(
                {"error": "An unexpected error occurred", "detail": str(e)}, status=500
            )


class StreamingResponseView(View):
    stored_stream: Generator[StreamResponse, None, None] = None

    @staticmethod
    def post(request, *args, **kwargs):
        use_case_type = request.POST.get("use_case_type")
        user_input = request.POST.get("user_input")

        if use_case_type != "OpenAIGptStreaming":
            return JsonResponse({"error": "Invalid use case for streaming"}, status=400)

        if not user_input:
            return JsonResponse({"error": "No input provided"}, status=400)

        use_case = OpenAIGptStreamingUseCase()
        StreamingResponseView.stored_stream = use_case.execute(
            user=request.user, content=user_input
        )

        return JsonResponse({"message": "ストリームが正常に初期化されました"})

    @staticmethod
    def get(request, *args, **kwargs):
        if not StreamingResponseView.stored_stream:
            return JsonResponse({"error": "No stream available"}, status=404)

        # ストリームデータをSSE（Server-Sent Events）形式に変換し、StreamingHttpResponseでラップする
        response = StreamingHttpResponse(
            streaming_content=OpenAIGptStreamingUseCase.convert_to_sse(
                StreamingResponseView.stored_stream
            ),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"

        return response


class StreamResultSaveView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        """
        保存処理を行うPOSTリクエストのエンドポイント
        """
        try:
            body = json.loads(request.body)
            content = body.get("content")

            if not content:
                return JsonResponse({"error": "Content is required"}, status=400)

            use_case = OpenAIGptStreamingUseCase()
            use_case.save(user=request.user, content=content)

            # 成功レスポンスを返す
            return JsonResponse(
                {"status": "success", "message": "データが保存されました"}
            )
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse(
                {"error": "Failed to save data", "detail": str(e)}, status=500
            )


class ClearChatLogsView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        """ChatLogsテーブルを全削除する（誰でも実行可・CSRF保護あり）"""
        try:
            deleted_count, _ = ChatLogs.objects.all().delete()
            return JsonResponse({"status": "success", "deleted": deleted_count})
        except Exception as e:
            return JsonResponse(
                {"error": "Failed to clear", "detail": str(e)}, status=500
            )
