import json
import logging
import re
from pathlib import Path

from video_cue.domain.valueobject.analysis import Analysis, InvalidAnalysis

logger = logging.getLogger(__name__)
MAX_JSON_BYTES = 8 * 1024 * 1024


class ResultUnavailable(ValueError):
    """1件の結果または media 保存先を読み込めないことを表す。"""


class ResultFiles:
    """Django が管理する結果フォルダーから解析結果を取得する。

    Attributes:
        root: 動画ごとの結果フォルダーを含む許可ディレクトリ。
    """

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ResultUnavailable(
                "解析結果の保存先がありません。管理者に確認してください。"
            )

    def directory(self, key: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            raise ResultUnavailable("解析結果が見つかりません。")
        directory = (self.root / key).resolve()
        if not directory.is_relative_to(self.root) or not directory.is_dir():
            raise ResultUnavailable("解析結果が見つかりません。")
        return directory

    def list(self) -> list[dict]:
        try:
            directories = sorted(self.root.iterdir())
            results = []
            for directory in directories:
                if directory.is_dir() and re.fullmatch(
                    r"[A-Za-z0-9_-]+", directory.name
                ):
                    try:
                        analysis = self.read(directory.name)
                        results.append({"key": directory.name, "analysis": analysis})
                    except (InvalidAnalysis, ResultUnavailable) as exc:
                        results.append({"key": directory.name, "error": str(exc)})
            return results
        except OSError as exc:
            logger.warning("Cannot list video cue results", exc_info=True)
            raise ResultUnavailable(
                "解析結果のフォルダーを読み取れません。アクセス権を確認してください。"
            ) from exc

    def read(self, key: str) -> Analysis:
        path = (self.directory(key) / "analysis.json").resolve()
        if not path.is_relative_to(self.directory(key)):
            raise InvalidAnalysis("解析 JSON の参照先が許可範囲外です。")
        try:
            with path.open("rb") as stream:
                content = stream.read(MAX_JSON_BYTES + 1)
            if len(content) > MAX_JSON_BYTES:
                raise InvalidAnalysis("解析 JSON が上限の8 MiBを超えています。")
            return Analysis.from_dict(json.loads(content))
        except FileNotFoundError as exc:
            raise ResultUnavailable(
                "解析が未完了です。結果 JSON の出力完了後に再読み込みしてください。"
            ) from exc
        except InvalidAnalysis:
            raise
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise InvalidAnalysis(
                "解析 JSON が壊れています。出力ファイルを確認してください。"
            ) from exc
        except OSError as exc:
            logger.warning("Cannot read video cue result %s", key, exc_info=True)
            raise ResultUnavailable(
                "解析 JSON を読み取れません。アクセス権を確認してください。"
            ) from exc

    def video(self, key: str, reference: str | None) -> Path | None:
        """JSON の参照を許可範囲内の MP4 に限定する。欠損・範囲外は None。"""
        if not reference:
            return None
        root = self.directory(key)
        try:
            relative = Path(reference)
            if relative.is_absolute() or relative.drive:
                return None
            path = (root / relative).resolve()
            if (
                path.is_relative_to(root)
                and path.suffix.lower() == ".mp4"
                and path.is_file()
            ):
                return path
        except (OSError, ValueError):
            return None
        return None
