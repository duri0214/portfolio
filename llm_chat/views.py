import json
from typing import Generator

from django.contrib.auth.models import User
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView
from dotenv import load_dotenv

from lib.llm.valueobject.completion import StreamResponse
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.chat import ChatDisplayService
from llm_chat.domain.valueobject.completion.riddle import GenderType, Gender
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.domain.factory.completion.use_case import UseCaseFactory
from llm_chat.domain.use_case.completion.chat import (
    OpenAIGptStreamingUseCase,
)
from llm_chat.domain.use_case.completion.riddle import RiddleUseCase
from llm_chat.forms import UserTextForm, RiddleCSVUploadForm
from llm_chat.models import ChatLogs, RiddleQuestion
import csv
import io
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction

# .env ファイルを読み込む
load_dotenv()


class IndexView(FormView):
    template_name = "llm_chat/index.html"
    form_class = UserTextForm
    success_url = reverse_lazy("llm:index")

    def get_initial(self):
        """フォームの初期値を設定します。"""
        initial = super().get_initial()
        login_user = self._get_login_user()

        initial_values = ChatDisplayService.get_initial_values(self.request, login_user)
        initial.update(initial_values)

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        login_user = self._get_login_user()
        chat_history = ChatLogRepository.find_chat_history(user=login_user)

        # JSON フォーマットデータをテンプレートに渡す
        context["chat_history"] = [log.to_display() for log in chat_history]
        context["is_superuser"] = self.request.user.is_superuser
        context["is_riddle_active"] = ChatDisplayService.is_riddle_active(chat_history)

        return context

    def _get_login_user(self):
        """ログインユーザーまたはデフォルトユーザー（pk=1）を取得します。"""
        return (
            self.request.user
            if self.request.user.is_authenticated
            else User.objects.get(pk=1)
        )


class SyncResponseView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        try:
            use_case_type = request.POST.get("use_case_type")
            user_input = request.POST.get("user_input")
            audio_file = request.FILES.get("audio_file")
            gender_val = request.POST.get("gender")

            if not use_case_type:
                return JsonResponse({"error": "No use case type provided"}, status=400)

            # セッションに use_case_type を保存（モデル変更なしで記憶するため）
            request.session["use_case_type"] = use_case_type

            # 性別のパース
            gender = None
            if gender_val:
                try:
                    gender = Gender(GenderType(gender_val))
                    # セッションに性別を保存（モデル変更なしで記憶するため）
                    request.session["riddle_gender"] = gender_val
                except ValueError:
                    pass

            # 使用するユースケースを切り替え
            try:
                if use_case_type == UseCaseType.OPENAI_SPEECH_TO_TEXT:
                    user_input = "N/A"
                use_case = UseCaseFactory.create(
                    use_case_type=use_case_type, audio_file=audio_file
                )
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)

            # ユースケースの実行
            try:
                if isinstance(use_case, RiddleUseCase):
                    message = use_case.execute(
                        user=request.user, content=user_input, gender=gender
                    )
                else:
                    message = use_case.execute(user=request.user, content=user_input)
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)

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

        if use_case_type != UseCaseType.OPENAI_GPT_STREAMING:
            return JsonResponse({"error": "Invalid use case for streaming"}, status=400)

        # セッションに use_case_type を保存
        request.session["use_case_type"] = use_case_type

        # 使用するユースケースを切り替え
        try:
            use_case = UseCaseFactory.create(use_case_type=use_case_type)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
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


class RiddleAdminView(View):
    @staticmethod
    def get(request, *args, **kwargs):
        questions = RiddleQuestion.objects.all()
        form = RiddleCSVUploadForm()
        return render(
            request,
            "llm_chat/riddle_admin.html",
            {"questions": questions, "form": form},
        )


class RiddleCSVUploadView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        form = RiddleCSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string)

            # order も question_text もユニークなので、
            # CSVでの一括更新を容易にするため、既存データを一度削除してから再投入する方式を採用。
            # トランザクション内で処理することで、エラー時は全削除をロールバックする。
            try:
                with transaction.atomic():
                    # 既存データを削除
                    RiddleQuestion.objects.all().delete()

                    created_count = 0
                    for row in reader:
                        if len(row) < 3:
                            continue
                        order, question_text, answer_text = row[0], row[1], row[2]
                        # CSVの内容を新規登録
                        RiddleQuestion.objects.create(
                            order=order,
                            question_text=question_text,
                            answer_text=answer_text,
                        )
                        created_count += 1

                    messages.success(
                        request,
                        f"CSVアップロード完了: {created_count} 件登録しました",
                    )
            except Exception as e:
                messages.error(
                    request, f"CSVアップロード中にエラーが発生しました: {str(e)}"
                )
        else:
            messages.error(request, "CSVファイルのアップロードに失敗しました。")

        return redirect("llm:riddle_admin")


class RiddleSampleCSVView(View):
    @staticmethod
    def get(request, *args, **kwargs):
        """サンプルCSVを出力する（以前のフォールバック2問）"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="riddle_sample.csv"'

        writer = csv.writer(response)
        # order, question_text, answer_text
        writer.writerow(
            [
                1,
                "はじめは4本足、途中から2本足、最後は3本足。それは何でしょう？",
                "人間",
            ]
        )
        writer.writerow(
            [
                2,
                "私は黒い服を着て、赤い手袋を持っている。夜には立っているが、朝になると寝る。何でしょう？",
                "たいまつ",
            ]
        )

        return response
