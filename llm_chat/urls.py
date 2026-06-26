from django.urls import path

from .views import (
    StreamingResponseView,
    IndexView,
    StreamResultSaveView,
    SyncResponseView,
    RokunoheMinutesRagView,
    ClearChatLogsView,
    RiddleAdminView,
    RiddleCSVUploadView,
    RiddleSampleCSVView,
    OpenAIRagPdfAdminView,
    OpenAIRagPdfUploadView,
    OpenAIRagPdfDeleteView,
    OpenAIRagPdfCollectionDeleteAllView,
    OpenAIRagPdfCollectionViewerView,
    OpenAIRagSamplePdfDownloadView,
    RokunohePdfDownloadView,
    RokunoheVectorDbResetView,
    RokunoheCollectionStatsView,
    RokunoheCollectionViewerView,
)

app_name = "llm"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path(
        "rokunohe-minutes/", RokunoheMinutesRagView.as_view(), name="rokunohe_minutes"
    ),
    path("riddle_admin/", RiddleAdminView.as_view(), name="riddle_admin"),
    path(
        "openai-rag-pdfs/",
        OpenAIRagPdfAdminView.as_view(),
        name="openai_rag_pdf_admin",
    ),
    path(
        "openai-rag-pdfs/upload/",
        OpenAIRagPdfUploadView.as_view(),
        name="openai_rag_pdf_upload",
    ),
    path(
        "openai-rag-pdfs/<int:pdf_id>/delete/",
        OpenAIRagPdfDeleteView.as_view(),
        name="openai_rag_pdf_delete",
    ),
    path(
        "openai-rag-pdfs/collection-delete-all/",
        OpenAIRagPdfCollectionDeleteAllView.as_view(),
        name="openai_rag_pdf_collection_delete_all",
    ),
    path(
        "openai-rag-pdfs/collection-viewer/",
        OpenAIRagPdfCollectionViewerView.as_view(),
        name="openai_rag_pdf_collection_viewer",
    ),
    path(
        "openai-rag-pdfs/samples/<path:filename>/",
        OpenAIRagSamplePdfDownloadView.as_view(),
        name="openai_rag_sample_pdf_download",
    ),
    path(
        "riddle_admin/upload/",
        RiddleCSVUploadView.as_view(),
        name="riddle_csv_upload",
    ),
    path(
        "riddle_admin/sample_csv/",
        RiddleSampleCSVView.as_view(),
        name="riddle_sample_csv",
    ),
    path("streaming/", StreamingResponseView.as_view(), name="streaming_response"),
    path("sync/", SyncResponseView.as_view(), name="sync_response"),
    path(
        "streaming/result_save/",
        StreamResultSaveView.as_view(),
        name="streaming_result_save",
    ),
    path("clear_chat_logs/", ClearChatLogsView.as_view(), name="clear_chat_logs"),
    path(
        "rokunohe-pdf-download/",
        RokunohePdfDownloadView.as_view(),
        name="rokunohe_pdf_download",
    ),
    path(
        "rokunohe-vector-db-reset/",
        RokunoheVectorDbResetView.as_view(),
        name="rokunohe_vector_db_reset",
    ),
    path(
        "rokunohe-collection-stats/",
        RokunoheCollectionStatsView.as_view(),
        name="rokunohe_collection_stats",
    ),
    path(
        "rokunohe-collection-viewer/",
        RokunoheCollectionViewerView.as_view(),
        name="rokunohe_collection_viewer",
    ),
]
