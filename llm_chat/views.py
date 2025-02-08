import json

from django.contrib.auth.models import User
from django.http import StreamingHttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView
from dotenv import load_dotenv

from lib.llm.llm_service import OpenAILlmCompletionStreamingService
from llm_chat.domain.repository.chat import ChatLogRepository
from llm_chat.domain.usecase.chat import (
    UseCase,
    GeminiUseCase,
    OpenAIGptUseCase,
    OpenAIGptStreamingUseCase,
    OpenAIDalleUseCase,
    OpenAITextToSpeechUseCase,
    OpenAISpeechToTextUseCase,
    OpenAIRagUseCase,
)
from llm_chat.forms import UserTextForm

# .env ファイルを読み込む
load_dotenv()


class IndexView(FormView):
    template_name = "llm_chat/index.html"
    form_class = UserTextForm
    success_url = reverse_lazy("llm:index")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        login_user = User.objects.get(pk=1)  # TODO: request.user.id
        context["chat_history"] = ChatLogRepository.find_chat_history(
            login_user
        ).order_by("created_at")

        context["is_superuser"] = self.request.user.is_superuser

        return context


class SyncResponseView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        try:
            use_case_type = request.POST.get("use_case_type")
            user_input = request.POST.get("user_input")
            audio_file = request.FILES.get("audio_file")

            if not use_case_type:
                return JsonResponse({"error": "No use case type provided"}, status=400)

            # 使用するユースケースを切り替え
            use_case: UseCase | None = None
            if use_case_type == "Gemini":
                use_case = GeminiUseCase()
            elif use_case_type == "OpenAIGpt":
                use_case = OpenAIGptUseCase()
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

            if not use_case:
                return JsonResponse(
                    {"error": "Invalid use case type provided"}, status=400
                )

            # ユースケースの実行
            result = use_case.execute(user=request.user, content=user_input)

            # 成功レスポンスを返す
            visible_results = [r for r in result if not r.invisible]
            return JsonResponse(
                {
                    "status": "success",
                    "message": f"{use_case_type} 処理が完了しました",
                    "result": visible_results[-1].to_dict(),
                }
            )

        except Exception as e:
            return JsonResponse(
                {"error": "An unexpected error occurred", "detail": str(e)}, status=500
            )


class StreamingResponseView(View):
    stored_stream = None

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
            OpenAILlmCompletionStreamingService.streaming_from_generator(
                generator=StreamingResponseView.stored_stream
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

            # 必要に応じてデータベースに保存
            # ChatLog.objects.create(content=content, timestamp=timestamp)

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
