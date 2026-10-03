import json
import os
import re
import shutil
import tempfile
from itertools import zip_longest
from pathlib import Path

from video_cue.domain.repository.local_results import (
    LocalResults,
    MAX_JSON_BYTES,
    ResultUnavailable,
)
from video_cue.domain.valueobject.analysis import Analysis

MAX_HIGHLIGHT_BYTES = 128 * 1024 * 1024
KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]+\Z")


def reject_nonfinite(value: str):
    raise ValueError(f"Invalid JSON number: {value}")


class UploadError(ValueError):
    """アップロードされた1件の成果物を受け付けられない理由。"""


class DuplicateResult(UploadError):
    """同じ ID に異なる解析結果が既に保存されていることを表す。"""


class StoredResults(LocalResults):
    """Django の media 配下に完成済みの解析結果だけを保存・取得する。"""

    def __init__(self, media_root: str | Path):
        root = Path(media_root).resolve() / "video_cue"
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ResultUnavailable("解析結果の保存先を使用できません。") from exc
        super().__init__(str(root))

    def save(self, key: str, analysis_file, highlight_file) -> bool:
        """一時領域で検証後に公開し、同一内容の再送は成功として扱う。"""
        if not KEY_PATTERN.fullmatch(key):
            raise UploadError(
                "動画 ID は英数字、ハイフン、アンダースコアのみ使用できます。"
            )
        raw = analysis_file.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise UploadError("解析 JSON が8 MiBの上限を超えています。")
        try:
            data = json.loads(raw, parse_constant=reject_nonfinite)
            parsed = Analysis.from_dict(data)
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise UploadError("解析 JSON の形式が不正です。") from exc
        if type(data["schema_version"]) is not int or data["schema_version"] != 2:
            raise UploadError("アップロードには schema_version 2 が必要です。")

        if parsed.events:
            if parsed.highlight != "highlights.mp4" or highlight_file is None:
                raise UploadError("イベントがある場合は highlights.mp4 が必要です。")
            if not highlight_file.name.lower().endswith(".mp4"):
                raise UploadError("ハイライト動画は MP4 形式が必要です。")
            if highlight_file.size > MAX_HIGHLIGHT_BYTES:
                raise UploadError("ハイライト動画が128 MiBの上限を超えています。")
        elif parsed.highlight is not None or highlight_file is not None:
            raise UploadError("イベント0件ではハイライト動画を送信しないでください。")

        # 元動画と個別クリップは共有しない。元動画名だけを表示用メタデータとして残す。
        source_name = Path(parsed.source.replace("\\", "/")).name
        if source_name in ("", ".", ".."):
            raise UploadError("元動画名が不正です。")
        data["input"]["path"] = source_name
        data["highlight_path"] = "highlights.mp4" if parsed.events else None
        for event in data["events"]:
            event["clip_path"] = None
        try:
            canonical = json.dumps(
                data, ensure_ascii=False, sort_keys=True, allow_nan=False
            ).encode("utf-8")
        except (UnicodeError, ValueError) as exc:
            raise UploadError("解析 JSON の形式が不正です。") from exc
        if len(canonical) > MAX_JSON_BYTES:
            raise UploadError("解析 JSON が8 MiBの上限を超えています。")

        stage = Path(tempfile.mkdtemp(prefix=".upload-", dir=self.root))
        try:
            (stage / "analysis.json").write_bytes(canonical)
            if highlight_file is not None:
                size = 0
                with (stage / "highlights.mp4").open("wb") as output:
                    for chunk in highlight_file.chunks():
                        size += len(chunk)
                        if size > MAX_HIGHLIGHT_BYTES:
                            raise UploadError(
                                "ハイライト動画が128 MiBの上限を超えています。"
                            )
                        output.write(chunk)
                with (stage / "highlights.mp4").open("rb") as stream:
                    header = stream.read(12)
                if size < 12 or header[4:8] != b"ftyp":
                    raise UploadError("ハイライト動画の MP4 形式が不正です。")
            target = self.root / key
            if target.exists() or target.is_symlink():
                return self._same_result(target, stage)
            try:
                os.rename(stage, target)
            except OSError:
                if target.exists() or target.is_symlink():
                    return self._same_result(target, stage)
                raise
            return True
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    @staticmethod
    def _same_result(target: Path, stage: Path) -> bool:
        if target.is_symlink() or not target.is_dir():
            raise DuplicateResult("同じ動画 ID は既に使用されています。")
        for name in ("analysis.json", "highlights.mp4"):
            current = target / name
            incoming = stage / name
            if current.exists() != incoming.exists():
                raise DuplicateResult("同じ動画 ID に異なる成果物が保存済みです。")
            if current.exists():
                if (
                    current.is_symlink()
                    or current.stat().st_size != incoming.stat().st_size
                ):
                    raise DuplicateResult("同じ動画 ID に異なる成果物が保存済みです。")
                with current.open("rb") as existing, incoming.open("rb") as received:
                    chunks = zip_longest(
                        iter(lambda: existing.read(64 * 1024), b""),
                        iter(lambda: received.read(64 * 1024), b""),
                    )
                    if any(left != right for left, right in chunks):
                        raise DuplicateResult(
                            "同じ動画 ID に異なる成果物が保存済みです。"
                        )
        return False
