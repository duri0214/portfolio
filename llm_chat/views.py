import os

from django.contrib.auth.models import User
from django.http import StreamingHttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView
from dotenv import load_dotenv

from lib.llm.llm_service import OpenAILlmCompletionStreamService
from lib.llm.valueobject.chat import Message, RoleType
from lib.llm.valueobject.config import OpenAIGptConfig
from llm_chat.domain.repository.chat import ChatLogRepository
from llm_chat.domain.usecase.chat import (
    UseCase,
    GeminiUseCase,
    OpenAIGptUseCase,
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

    def form_valid(self, form):
        # TODO: StreamResponseView のPOSTに持っていけるはず
        form_data = form.cleaned_data
        login_user = User.objects.get(pk=1)  # TODO: request.user.id

        use_case_type = form_data["use_case_type"]
        use_case: UseCase | None = None
        content: str = form_data["question"]
        if use_case_type == "Gemini":
            use_case = GeminiUseCase()
            content = form_data["question"]
        elif use_case_type == "OpenAIGpt":
            # Questionは何を入れてもいい（処理されない）
            use_case = OpenAIGptUseCase()
            content = form_data["question"]
        elif use_case_type == "OpenAIDalle":
            use_case = OpenAIDalleUseCase()
            content = form_data["question"]
        elif use_case_type == "OpenAITextToSpeech":
            use_case = OpenAITextToSpeechUseCase()
            content = form_data["question"]
        elif use_case_type == "OpenAISpeechToText":
            # Questionは何を入れてもいい（処理されない）
            audio_file = form_data.get("audio_file")
            use_case = OpenAISpeechToTextUseCase(audio_file)
            content = "N/A"
        elif use_case_type == "OpenAIRag":
            use_case = OpenAIRagUseCase()
            content = form_data["question"]

        use_case.execute(user=login_user, content=content)

        return super().form_valid(form)


class StreamResponseView(View):
    stored_stream = None

    @staticmethod
    def post(request, *args, **kwargs):
        user_input = request.POST.get("user_input")
        if not user_input:
            return JsonResponse({"error": "No input provided"}, status=400)

        # TODO: use_case_type を使って use-case を呼び出す
        service = OpenAILlmCompletionStreamService(
            config=OpenAIGptConfig(
                api_key=os.getenv("OPENAI_API_KEY"),
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=500,
            )
        )

        chat_history = [Message(role=RoleType.USER, content=user_input)]

        StreamResponseView.stored_stream = lambda: service.stream_chunks(chat_history)
        return JsonResponse({"message": "ストリームが正常に初期化されました"})

    @staticmethod
    def get(request, *args, **kwargs):
        if not StreamResponseView.stored_stream:
            return JsonResponse({"error": "No stream available"}, status=404)

        stream_generator = StreamResponseView.stored_stream()

        # ストリームデータをSSE（Server-Sent Events）形式に変換し、StreamingHttpResponseでラップする
        response = StreamingHttpResponse(
            OpenAILlmCompletionStreamService.stream_from_generator(
                generator=stream_generator
            ),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"

        return response
