import csv
import io
import json
import logging
import math
import os
import traceback
from datetime import date, timedelta
from pathlib import Path
from typing import Generator

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.http import (
    FileResponse,
    Http404,
    StreamingHttpResponse,
    JsonResponse,
    HttpResponse,
)
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import FormView
from dotenv import load_dotenv

from lib.llm.valueobject.completion import StreamResponse
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.domain.factory.completion.use_case import UseCaseFactory
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.repository.completion.rag import (
    OpenAIRagPdfRepository,
    OpenAIRagVectorRepository,
)
from llm_chat.domain.repository.completion.rokunohe_minutes import (
    RokunoheMinutesRagRepository,
)
from llm_chat.domain.service.completion.rag import OpenAIRagPdfImportService
from llm_chat.domain.service.chat import ChatDisplayService
from llm_chat.domain.service.completion.rokunohe_minutes import (
    RokunoheMinutesCollectionStatsService,
    RokunoheMinutesRagService,
)
from llm_chat.domain.use_case.completion.chat import (
    OpenAIGptStreamingUseCase,
)
from llm_chat.domain.use_case.completion.riddle import (
    RiddleUseCase,
    RiddleStreamingUseCase,
)
from llm_chat.domain.valueobject.completion.riddle import (
    GenderType,
    Gender,
    SessionState,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.forms import UserTextForm, RiddleCSVUploadForm, OpenAIRagPdfUploadForm
from llm_chat.models import RiddleQuestion, OpenAIRagPdf

# .env ファイルを読み込む
load_dotenv()


# ロガーの設定
logger = logging.getLogger(__name__)


def _get_login_user(request):
    """ログインユーザーまたはデフォルトユーザー（pk=1）を取得します。"""
    return request.user if request.user.is_authenticated else User.objects.get(pk=1)


def _parse_source_date_range(request) -> tuple[int | None, int | None]:
    """
    管理画面の任意期間入力をYYYYMMDD整数へ変換します。

    未指定なら既存どおり直近1年基準に任せるため、上下限ともNoneを返します。
    終了日だけを指定した場合は、意図しない広範囲処理を避けるためエラーにします。
    """
    return _parse_source_date_range_values(
        source_date_from_value=request.POST.get("source_date_from", ""),
        source_date_to_value=request.POST.get("source_date_to", ""),
    )


def _parse_source_date_range_values(
    *,
    source_date_from_value: str | None,
    source_date_to_value: str | None,
) -> tuple[int | None, int | None]:
    """
    任意期間入力をYYYYMMDD整数へ変換します。

    POSTで実行するPDF取り込みと、GETで表示するcollection集計の両方で使います。
    終了日だけを指定した場合は、意図しない広範囲処理を避けるためエラーにします。
    """
    source_date_from = _parse_optional_source_date(source_date_from_value)
    source_date_to = _parse_optional_source_date(source_date_to_value)
    if source_date_from is None and source_date_to is not None:
        raise ValueError("処理期間の終了日を指定する場合は開始日も指定してください。")
    if (
        source_date_from is not None
        and source_date_to is not None
        and source_date_from > source_date_to
    ):
        raise ValueError("処理期間の開始日は終了日以前にしてください。")
    return source_date_from, source_date_to


def _parse_optional_source_date(value: str | None) -> int | None:
    raw_value = (value or "").strip()
    if not raw_value:
        return None
    try:
        parsed_date = date.fromisoformat(raw_value)
    except ValueError as e:
        raise ValueError("処理期間はYYYY-MM-DD形式で指定してください。") from e
    return int(parsed_date.strftime("%Y%m%d"))


def _build_source_date_command_options(
    *,
    source_date_from: int | None,
    source_date_to: int | None,
) -> dict[str, int]:
    options: dict[str, int] = {}
    if source_date_from is not None:
        options["source_date_from"] = source_date_from
    if source_date_to is not None:
        options["source_date_to"] = source_date_to
    return options


def _build_source_date_period_label(
    *,
    source_date_from: int | None,
    source_date_to: int | None,
) -> str:
    if source_date_from is None:
        return "直近1年"
    if source_date_to is None:
        return f"{_format_source_date(source_date_from)}〜指定なし"
    return (
        f"{_format_source_date(source_date_from)}"
        f"〜{_format_source_date(source_date_to)}"
    )


def _format_source_date(source_date: int) -> str:
    raw_value = str(source_date)
    return f"{raw_value[:4]}-{raw_value[4:6]}-{raw_value[6:8]}"


class IndexView(FormView):
    template_name = "llm_chat/index.html"
    form_class = UserTextForm
    success_url = reverse_lazy("llm:index")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["rag_pdf_choices"] = OpenAIRagPdfRepository.list_active_choices()
        return kwargs

    def get_initial(self):
        """フォームの初期値を設定します。"""
        initial = super().get_initial()
        login_user = _get_login_user(self.request)

        initial_values = ChatDisplayService.get_initial_values(self.request, login_user)
        initial.update(initial_values)

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        login_user = _get_login_user(self.request)
        chat_history = ChatDisplayService.get_regular_chat_history(login_user)

        # JSON フォーマットデータをテンプレートに渡す
        context["chat_history"] = [log.to_display() for log in chat_history]
        context["is_superuser"] = self.request.user.is_superuser
        context["is_riddle_active"] = ChatDisplayService.is_riddle_active(chat_history)
        context["rag_pdf_count"] = OpenAIRagPdf.objects.filter(is_active=True).count()

        return context


class OpenAIRagPdfAdminView(UserPassesTestMixin, View):
    """
    OpenAI RAGで使用するPDFの登録・一覧表示を行う管理者用ビュー。
    """

    raise_exception = True

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, *args, **kwargs):
        context = {
            "form": OpenAIRagPdfUploadForm(),
            "pdfs": OpenAIRagPdf.objects.all(),
            "sample_pdfs": self._get_sample_pdf_names(),
        }
        return render(request, "llm_chat/openai_rag_pdf_admin.html", context)

    @staticmethod
    def _get_sample_pdf_names() -> list[str]:
        sample_dir = Path(settings.BASE_DIR) / "lib" / "llm" / "pdf_sample"
        if not sample_dir.exists():
            return []
        return sorted(path.name for path in sample_dir.glob("*.pdf"))


class OpenAIRagPdfUploadView(UserPassesTestMixin, View):
    """
    OpenAI RAG用PDFを保存し、Vector DBへ登録する管理者用ビュー。
    """

    raise_exception = True

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        form = OpenAIRagPdfUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            for error in form.errors.values():
                messages.warning(request, error)
            return redirect("llm:openai_rag_pdf_admin")

        pdf = form.save()
        try:
            imported_count = OpenAIRagPdfImportService().import_pdf(pdf.id)
            if imported_count:
                messages.success(
                    request,
                    f"PDFを登録しました。Vector DB登録ページ数: {imported_count}件",
                )
            else:
                messages.warning(
                    request,
                    "PDFを保存しましたが、抽出できる本文がありませんでした。",
                )
        except Exception as e:
            logger.error(f"OpenAIRagPdfUploadView Error: {str(e)}")
            logger.error(traceback.format_exc())
            messages.error(request, f"PDFのVector DB登録に失敗しました: {str(e)}")
        return redirect("llm:openai_rag_pdf_admin")


class OpenAIRagPdfDeleteView(UserPassesTestMixin, View):
    """
    OpenAI RAG用PDFと、そのPDF由来のVector DBチャンクを削除する管理者用ビュー。
    """

    raise_exception = True

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, pdf_id, *args, **kwargs):
        try:
            pdf_source = OpenAIRagPdfRepository.find_active(pdf_id)
            deleted_count = OpenAIRagVectorRepository(
                api_key=os.getenv("OPENAI_API_KEY") or ""
            ).delete_pdf_documents(pdf_source)
            pdf = OpenAIRagPdf.objects.get(id=pdf_id)
            pdf.file.delete(save=False)
            pdf.delete()
            messages.success(
                request,
                f"PDFを削除しました。Vector DB削除件数: {deleted_count}件",
            )
        except OpenAIRagPdf.DoesNotExist:
            messages.warning(request, "削除対象のPDFが見つかりません。")
        return redirect("llm:openai_rag_pdf_admin")


class OpenAIRagSamplePdfDownloadView(UserPassesTestMixin, View):
    """
    lib/llm/pdf_sample 配下のPDFをサンプルとしてダウンロードするビュー。
    """

    raise_exception = True

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, filename, *args, **kwargs):
        sample_dir = Path(settings.BASE_DIR) / "lib" / "llm" / "pdf_sample"
        file_path = (sample_dir / filename).resolve()
        if sample_dir.resolve() not in file_path.parents or file_path.suffix != ".pdf":
            raise Http404("PDF sample not found")
        if not file_path.exists():
            raise Http404("PDF sample not found")
        return FileResponse(
            file_path.open("rb"),
            as_attachment=True,
            filename=file_path.name,
        )


class RokunoheMinutesRagView(View):
    """
    六戸町会議録専用のRAGチャットビュー。
    """

    def get(self, request, *args, **kwargs):
        login_user = _get_login_user(request)
        chat_history = ChatLogRepository.find_chat_history(
            user=login_user, use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG
        )
        form = UserTextForm(initial={"use_case_type": UseCaseType.ROKUNOHE_MINUTES_RAG})

        context = {
            "chat_history": [log.to_display() for log in chat_history],
            "form": form,
            "use_case_type": UseCaseType.ROKUNOHE_MINUTES_RAG,
            "is_superuser": request.user.is_superuser,
        }
        return render(request, "llm_chat/rokunohe_minutes.html", context)

    def post(self, request, *args, **kwargs):
        user_input = request.POST.get("user_input")
        if not user_input:
            return JsonResponse({"error": "No user input provided"}, status=400)

        try:
            login_user = _get_login_user(request)
            use_case = UseCaseFactory.create(UseCaseType.ROKUNOHE_MINUTES_RAG)
            message = use_case.execute(user=login_user, content=user_input)
            return JsonResponse(
                {
                    "status": "success",
                    "result": message.to_display(),
                }
            )
        except Exception as e:
            logger.error(f"RokunoheMinutesRagView Error: {str(e)}")
            logger.error(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=500)


class RokunohePdfDownloadView(UserPassesTestMixin, View):
    """
    六戸町会議録PDFの取得・ベクトル化を管理画面から起動するビュー。

    このViewは、管理者の同意確認、六戸町会議録QAの会話履歴リセット、
    PDFダウンロード管理コマンド実行、取り込み後の初回サマリー作成を1回のPOSTで行います。
    PDFの巡回・保存・Chroma登録の詳細は `rokunohe_pdf_download` コマンドへ委譲します。
    """

    raise_exception = True
    command_name = "rokunohe_pdf_download"
    success_message = "六戸町会議録PDFの直近1年分の取得・ベクトル化処理を実行しました。"
    reset_consent_value = "1"

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        """
        同意値を確認してから会話履歴を消し、PDF取得コマンドと初回サマリー生成を実行します。

        PDF取得・ベクトル化によってRAGの根拠データが変わる可能性があるため、
        古い会話履歴を残さず、取り込み後のcollectionをもとにしたサマリーを
        チャット履歴の先頭として作り直します。
        """
        if request.POST.get("reset_consent") != self.reset_consent_value:
            messages.warning(
                request,
                "会話履歴のリセットに同意してから実行してください。",
            )
            return redirect("llm:rokunohe_minutes")

        try:
            source_date_from, source_date_to = _parse_source_date_range(request)
            command_options = _build_source_date_command_options(
                source_date_from=source_date_from,
                source_date_to=source_date_to,
            )
        except ValueError as e:
            messages.warning(request, str(e))
            return redirect("llm:rokunohe_minutes")

        login_user = _get_login_user(request)
        ChatLogRepository.clear_history(
            user=login_user,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        try:
            call_command(self.command_name, **command_options)
            self._save_initial_summary(login_user)
            messages.success(
                request,
                self._build_success_message(
                    source_date_from=source_date_from,
                    source_date_to=source_date_to,
                ),
            )
        except CommandError as e:
            messages.warning(request, str(e))
        return redirect("llm:rokunohe_minutes")

    @staticmethod
    def _save_initial_summary(user: User) -> None:
        service = RokunoheMinutesRagService()
        summary = service.generate_initial_summary(user)
        ChatLogRepository.insert(summary)

    def _build_success_message(
        self,
        *,
        source_date_from: int | None,
        source_date_to: int | None,
    ) -> str:
        if source_date_from is None:
            return self.success_message
        return (
            "六戸町会議録PDFの指定期間分の取得・ベクトル化処理を実行しました。"
            f" 対象期間: {_format_source_date(source_date_from)}"
            f"〜{_format_source_date(source_date_to) if source_date_to else '指定なし'}"
        )


class RokunoheVectorDbResetView(UserPassesTestMixin, View):
    """
    六戸町会議録RAGのChroma DB collectionをリセットする管理者用ビュー。
    """

    raise_exception = True
    reset_consent_value = "1"
    success_message = "六戸町会議録RAGのVector DBコレクションをリセットしました。"

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        if request.POST.get("reset_collection_consent") != self.reset_consent_value:
            messages.warning(
                request,
                "Vector DBコレクションのリセットに同意してから実行してください。",
            )
            return redirect("llm:rokunohe_minutes")

        login_user = _get_login_user(request)
        repository = RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )
        deleted_count = repository.reset_collection()
        ChatLogRepository.clear_history(
            user=login_user,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        messages.success(request, f"{self.success_message} 削除件数: {deleted_count}件")
        return redirect("llm:rokunohe_minutes")


class RokunoheCollectionStatsView(UserPassesTestMixin, View):
    """
    六戸町会議録RAGのcollection集計を表示する管理者用ビュー。

    Chroma DBに登録済みの本文チャンクを、LLMなし・DB保存なしでその場集計します。
    View自身はGETパラメータの期間指定を解決し、頻出語、PDF別ボリューム、
    日付別ボリュームをテンプレートへ渡すだけに責務を限定します。
    """

    raise_exception = True

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, *args, **kwargs):
        """
        collection集計を実行し、結果を表示します。

        期間未指定時は直近1年を対象にします。終了日だけが指定された場合など、
        期間指定が不正なときは警告メッセージを出して六戸町会議録QAへ戻します。
        """
        try:
            source_date_from, source_date_to = _parse_source_date_range_values(
                source_date_from_value=request.GET.get("source_date_from", ""),
                source_date_to_value=request.GET.get("source_date_to", ""),
            )
            service = RokunoheMinutesCollectionStatsService(
                source_date_from=source_date_from,
                source_date_to=source_date_to,
            )
            stats = service.build_stats()
        except ValueError as e:
            messages.warning(request, str(e))
            return redirect("llm:rokunohe_minutes")
        except Exception as e:
            logger.error(f"RokunoheCollectionStatsView Error: {str(e)}")
            logger.error(traceback.format_exc())
            messages.error(request, f"collection集計の表示に失敗しました: {str(e)}")
            return redirect("llm:rokunohe_minutes")

        period_label = _build_source_date_period_label(
            source_date_from=source_date_from,
            source_date_to=source_date_to,
        )
        context = {
            "stats": stats,
            "period_label": period_label,
            "source_date_from": (
                _format_source_date(source_date_from) if source_date_from else ""
            ),
            "source_date_to": (
                _format_source_date(source_date_to) if source_date_to else ""
            ),
        }
        return render(request, "llm_chat/rokunohe_collection_stats.html", context)


class RokunoheCollectionViewerView(UserPassesTestMixin, View):
    """
    六戸町会議録RAGのChroma DB collection内容を確認する管理者用ビュー。

    Chroma DBに入っている本文チャンクを、人間が点検できるページング一覧へ変換します。
    query_typeがrecent_yearのときは、PDF取得やcollection集計と同じ直近1年基準で
    Repositoryへsource_date_fromを渡します。
    """

    raise_exception = True
    default_per_page = 100
    per_page_options = (50, 100, 200, 500)
    recent_year_query_type = "recent_year"

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, *args, **kwargs):
        """
        ページング条件と絞り込み条件を解決し、collection一覧を表示します。

        total_countと表示データの両方に同じsource_date_fromを渡すことで、
        「直近1年」表示時のページ数と実データがずれないようにします。
        """
        per_page = self._get_per_page(request)
        current_page = self._get_current_page(request)
        query_type = self._get_query_type(request)
        source_date_from = self._get_source_date_from(query_type)
        offset = (current_page - 1) * per_page
        repository = RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )
        total_count = repository.count_collection_items(
            source_date_from=source_date_from
        )
        total_pages = max(math.ceil(total_count / per_page), 1)
        if current_page > total_pages:
            current_page = total_pages
            offset = (current_page - 1) * per_page

        collection_items = repository.list_collection_items(
            limit=per_page,
            offset=offset,
            source_date_from=source_date_from,
        )
        context = {
            "collection_items": collection_items,
            "current_page": current_page,
            "has_next_page": current_page < total_pages,
            "has_previous_page": current_page > 1,
            "next_page": current_page + 1,
            "page_start": offset + 1 if total_count else 0,
            "page_end": offset + len(collection_items),
            "per_page": per_page,
            "per_page_options": self.per_page_options,
            "previous_page": current_page - 1,
            "query_type": query_type,
            "query_type_label": self._get_query_type_label(query_type),
            "total_count": total_count,
            "total_pages": total_pages,
        }
        return render(request, "llm_chat/rokunohe_collection_viewer.html", context)

    def _get_per_page(self, request) -> int:
        try:
            per_page = int(request.GET.get("per_page", self.default_per_page))
        except (TypeError, ValueError):
            return self.default_per_page

        if per_page not in self.per_page_options:
            return self.default_per_page
        return per_page

    @staticmethod
    def _get_current_page(request) -> int:
        try:
            page = int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            return 1

        return max(page, 1)

    def _get_source_date_from(self, query_type: str) -> int | None:
        if query_type != self.recent_year_query_type:
            return None

        recent_year_start = timezone.localdate() - timedelta(days=365)
        return int(recent_year_start.strftime("%Y%m%d"))

    def _get_query_type(self, request) -> str:
        query_type = request.GET.get("query_type", "")
        if query_type == self.recent_year_query_type:
            return query_type
        return ""

    def _get_query_type_label(self, query_type: str) -> str:
        if query_type == self.recent_year_query_type:
            return "直近1年"
        return "全件"


class SyncResponseView(View):
    """
    同期的にLLMからのレスポンスを取得し、結果を返すビューです。
    画像/音声/RAG などの同期系ユースケース専用。
    チャット系（OpenAI GPT / Gemini / Streaming）はストリーミング固定のため、
    ここでは不正な use_case_type として 400 を返します。
    """

    @staticmethod
    def post(request, *args, **kwargs):
        """
        POSTリクエストを処理し、選択されたユースケースに基づいて同期処理を実行します。
        """
        try:
            use_case_type = request.POST.get("use_case_type")
            user_input = request.POST.get("user_input")
            audio_file = request.FILES.get("audio_file")
            gender_val = request.POST.get("gender")
            rag_pdf_id = request.POST.get("rag_pdf")

            if not use_case_type:
                return JsonResponse({"error": "No use case type provided"}, status=400)
            if use_case_type in (
                UseCaseType.OPENAI_GPT,
                UseCaseType.GEMINI,
                UseCaseType.OPENAI_GPT_STREAMING,
            ):
                return JsonResponse({"error": "Invalid use case for sync"}, status=400)

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
                if use_case_type == UseCaseType.OPENAI_RAG:
                    message = use_case.execute(
                        user=request.user,
                        content=user_input,
                        rag_pdf_id=rag_pdf_id,
                    )
                    request.session["rag_pdf_id"] = rag_pdf_id
                elif isinstance(use_case, RiddleUseCase):
                    message = use_case.execute(
                        user=request.user, content=user_input, gender=gender
                    )
                else:
                    message = use_case.execute(user=request.user, content=user_input)
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)

            # 成功レスポンスを返す
            success_message = f"{use_case_type} 処理が完了しました"
            if isinstance(use_case, RiddleUseCase) and message.next_riddle_state:
                state_map = {
                    SessionState.USER_INPUT.value: "回答をお待ちしています",
                    SessionState.EVALUATE.value: "回答を評価しています...",
                    SessionState.START.value: "新しい問題を出題します",
                    SessionState.FINISHED.value: "なぞなぞを終了しました",
                }
                # カンマ区切りの場合は最後の状態を代表メッセージとする（UI側で詳細は処理する）
                last_state = message.next_riddle_state.split(",")[-1]
                success_message = state_map.get(last_state, success_message)

            return JsonResponse(
                {
                    "status": "success",
                    "message": success_message,
                    "result": message.to_display(),
                }
            )

        except Exception as e:
            logger.error(f"SyncResponseView Error: {str(e)}")
            logger.error(traceback.format_exc())
            return JsonResponse(
                {"error": "An unexpected error occurred", "detail": str(e)}, status=500
            )


class StreamingResponseView(View):
    """
    LLMからのストリーミングレスポンスを制御するビューです。
    """

    stored_stream: Generator[StreamResponse, None, None] = None

    @staticmethod
    def post(request, *args, **kwargs):
        """
        ストリームを初期化し、セッションに保存します。
        """
        try:
            use_case_type = request.POST.get("use_case_type")
            user_input = request.POST.get("user_input")

            if use_case_type not in (
                UseCaseType.OPENAI_GPT_STREAMING,
                UseCaseType.RIDDLE,
            ):
                return JsonResponse(
                    {"error": "Invalid use case for streaming"}, status=400
                )

            # セッションに use_case_type を保存
            request.session["use_case_type"] = use_case_type

            # 使用するユースケースを切り替え
            try:
                if use_case_type == UseCaseType.RIDDLE:
                    use_case = RiddleStreamingUseCase(
                        config=OpenAIGptConfig(
                            api_key=os.getenv("OPENAI_API_KEY") or "",
                            max_tokens=4000,
                            model=ModelName.GPT_5_MINI,
                        )
                    )
                else:
                    use_case = UseCaseFactory.create(use_case_type=use_case_type)
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)
            try:
                if use_case_type == UseCaseType.RIDDLE:
                    gender_val = request.POST.get("gender")
                    gender = None
                    if gender_val:
                        try:
                            gender = Gender(GenderType(gender_val))
                            request.session["riddle_gender"] = gender_val
                        except ValueError:
                            pass
                    StreamingResponseView.stored_stream = use_case.execute(
                        user=request.user, content=user_input, gender=gender
                    )
                else:
                    StreamingResponseView.stored_stream = use_case.execute(
                        user=request.user, content=user_input
                    )
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)

            return JsonResponse({"message": "ストリームが正常に初期化されました"})

        except Exception as e:
            logger.error(f"StreamingResponseView.post Error: {str(e)}")
            logger.error(traceback.format_exc())
            return JsonResponse(
                {"error": "An unexpected error occurred", "detail": str(e)}, status=500
            )

    @staticmethod
    def get(request, *args, **kwargs):
        """
        保存されたストリームからデータを取得し、SSE形式で返します。
        """
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
    """
    ストリーミング結果を保存するビューです。
    """

    @staticmethod
    def post(request, *args, **kwargs):
        """
        ストリームで受け取った最終的なコンテンツをデータベースに保存します。
        """
        try:
            body = json.loads(request.body)
            content = body.get("content")

            if not content:
                return JsonResponse({"error": "Content is required"}, status=400)

            use_case_type = request.session.get("use_case_type")
            if use_case_type == UseCaseType.RIDDLE:
                use_case = RiddleStreamingUseCase(
                    config=OpenAIGptConfig(
                        api_key=os.getenv("OPENAI_API_KEY") or "",
                        max_tokens=4000,
                        model=ModelName.GPT_5_MINI,
                    )
                )
                use_case.save(user=request.user, content=content)
            else:
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
    """
    チャット履歴を削除するビューです。
    """

    @staticmethod
    def post(request, *args, **kwargs):
        """
        指定されたユーザー（またはデフォルトユーザー）のチャット履歴を削除します。
        use_case_type が指定されている場合は、そのユースケースに限定します。
        """
        try:
            login_user = _get_login_user(request)
            use_case_type = request.POST.get("use_case_type")
            count = ChatLogRepository.clear_history(
                user=login_user, use_case_type=use_case_type
            )
            return JsonResponse({"status": "success", "deleted": count})
        except Exception as e:
            logger.error(f"ClearChatLogsView Error: {str(e)}")
            return JsonResponse(
                {"error": "Failed to clear", "detail": str(e)}, status=500
            )


class RiddleAdminView(View):
    """
    なぞなぞの管理画面を表示するビューです。
    """

    @staticmethod
    def get(request, *args, **kwargs):
        """
        なぞなぞ一覧とアップロードフォームを表示します。
        """
        questions = RiddleQuestion.objects.all()
        form = RiddleCSVUploadForm()
        return render(
            request,
            "llm_chat/riddle_admin.html",
            {"questions": questions, "form": form},
        )


class RiddleCSVUploadView(View):
    """
    なぞなぞのCSVファイルをアップロードし、登録するビューです。
    """

    @staticmethod
    def post(request, *args, **kwargs):
        """
        CSVファイルを読み込み、なぞなぞデータを一括登録します。
        """
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
    """
    サンプルCSVをダウンロードするためのビューです。
    """

    @staticmethod
    def get(request, *args, **kwargs):
        """
        サンプルのなぞなぞデータを含むCSVファイルを生成して返します。
        """
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
