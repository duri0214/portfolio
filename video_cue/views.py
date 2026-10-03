import re
from functools import wraps

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_safe

from video_cue.domain.repository.local_results import LocalResults, ResultUnavailable
from video_cue.domain.valueobject.analysis import InvalidAnalysis


def staff_view(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_staff:
            return render(request, "video_cue/access.html", status=403)
        return view(request, *args, **kwargs)

    return require_safe(wrapped)


def repository() -> LocalResults:
    return LocalResults(settings.VIDEO_CUE_RESULTS_ROOT, settings.VIDEO_CUE_SOURCE_ROOT)


@staff_view
def index(request):
    try:
        return render(request, "video_cue/index.html", {"results": repository().list()})
    except ResultUnavailable as exc:
        return render(request, "video_cue/index.html", {"error": str(exc)}, status=503)


@staff_view
def detail(request, key: str):
    try:
        repo = repository()
        repo.directory(key)
    except ResultUnavailable as exc:
        raise Http404(str(exc)) from exc
    try:
        analysis = repo.read(key)
    except (InvalidAnalysis, ResultUnavailable) as exc:
        status = 422 if isinstance(exc, InvalidAnalysis) else 409
        return render(
            request,
            "video_cue/detail.html",
            {"key": key, "error": str(exc)},
            status=status,
        )

    def media_url(
        kind: str, reference: str | None, *, source: bool = False
    ) -> str | None:
        if repo.video(key, reference, source=source):
            return reverse("video_cue:media", args=[key, kind])
        return None

    highlight = media_url("highlight", analysis.highlight)
    source = media_url("source", analysis.source, source=True)
    events = [
        {
            "start": event.start,
            "end": event.end,
            "duration": event.duration,
            "peak": event.peak,
            "highlight_start": event.highlight_start,
            "clip_url": media_url(str(index), event.clip),
        }
        for index, event in enumerate(analysis.events)
    ]
    player = {"events": events, "highlight_url": highlight, "source_url": source}
    return render(
        request,
        "video_cue/detail.html",
        {
            "key": key,
            "analysis": analysis,
            "events": events,
            "player": player,
            "highlight_url": highlight,
            "source_url": source,
            "highlight_missing": bool(analysis.highlight and not highlight),
        },
    )


def file_chunks(stream, remaining: int):
    try:
        while remaining > 0:
            chunk = stream.read(min(64 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        stream.close()


@staff_view
def media(request, key: str, kind: str):
    """許可済み参照だけを配信し、ブラウザーの単一 byte Range に応答する。"""
    try:
        repo = repository()
        analysis = repo.read(key)
        if kind == "highlight":
            path = repo.video(key, analysis.highlight)
        elif kind == "source":
            path = repo.video(key, analysis.source, source=True)
        elif (
            kind.isascii()
            and kind.isdecimal()
            and len(kind) < 10
            and int(kind) < len(analysis.events)
        ):
            path = repo.video(key, analysis.events[int(kind)].clip)
        else:
            path = None
        if path is None:
            raise Http404("動画がないか、参照先が許可されていません。")
        stream = path.open("rb")
    except (OSError, InvalidAnalysis, ResultUnavailable) as exc:
        raise Http404(
            "動画を読み込めません。解析結果と動画の配置を確認してください。"
        ) from exc

    size = stream.seek(0, 2)
    stream.seek(0)
    start, end = 0, size - 1
    range_header = request.headers.get("Range")
    if range_header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
        try:
            if not match or not any(match.groups()):
                raise ValueError
            first, last = match.groups()
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:
                suffix = int(last)
                if suffix <= 0:
                    raise ValueError
                start = max(0, size - suffix)
            if start > end or start >= size:
                raise ValueError
        except ValueError:
            stream.close()
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            response["Accept-Ranges"] = "bytes"
            return response
    length = end - start + 1
    status = 206 if range_header else 200
    if request.method == "HEAD":
        stream.close()
        response = HttpResponse(content_type="video/mp4", status=status)
    elif range_header:
        stream.seek(start)
        response = FileResponse(stream, content_type="video/mp4", status=status)
        response.streaming_content = file_chunks(stream, length)
    else:
        response = FileResponse(stream, content_type="video/mp4")
    response["Content-Length"] = str(length)
    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "private, no-store"
    if range_header:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    return response
