from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.views.generic import FormView
from dotenv import load_dotenv

from llm_chat.domain.usecase.llm import (
    UseCase,
    GeminiUseCase,
    OpenAIGptUseCase,
    OpenAIDalleUseCase,
    OpenAITextToSpeechUseCase,
    OpenAISpeechToTextUseCase,
)
from llm_chat.forms import UserTextForm
from llm_chat.models import ChatLogs

# .env ファイルを読み込む
load_dotenv()


class IndexView(FormView):
    template_name = "llm_chat/index.html"
    form_class = UserTextForm
    success_url = reverse_lazy("llm:index")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        login_user = User.objects.get(pk=1)  # TODO: request.user.id
        context["chat_logs"] = ChatLogs.objects.filter(user=login_user).order_by(
            "created_at"
        )

        return context

    def form_valid(self, form):
        form_data = form.cleaned_data
        login_user = User.objects.get(pk=1)  # TODO: request.user.id

        use_case_type = "OpenAIGpt"  # TODO: ドロップダウンでモードを決める？
        use_case: UseCase | None = None
        content: str | None = form_data["question"]
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
            use_case = OpenAISpeechToTextUseCase()
            content = None

        use_case.execute(user=login_user, content=content)

        return super().form_valid(form)