from pathlib import Path

from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.views.generic import FormView
from dotenv import load_dotenv

from config.settings import MEDIA_ROOT
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
            # TODO: UseCaseのなかに整理したい
            audio_file = form_data.get("audio_file")
            if not audio_file:
                raise ValueError("音声ファイルが指定されていません")
            relative_path = f"llm_chat/audios/{audio_file.name}"
            save_path = Path(MEDIA_ROOT) / relative_path
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in audio_file.chunks():
                    f.write(chunk)

            # Questionは何を入れてもいい（処理されない）
            use_case = OpenAISpeechToTextUseCase(relative_path)
            content = "N/A"
        elif use_case_type == "OpenAIRag":
            use_case = OpenAIRagUseCase()
            content = form_data["question"]

        use_case.execute(user=login_user, content=content)

        return super().form_valid(form)
