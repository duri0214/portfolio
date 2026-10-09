"""Apacheアクセスログをダッシュボード表示用の件数へ集計する。"""

import os
import zlib
from datetime import datetime
from glob import glob
from pathlib import Path

from dotenv import load_dotenv

from lib.apache_access.domain.service.access_log_aggregator import (
    ApacheAccessLogAggregator,
)
from lib.apache_access.domain.valueobject.traffic import (
    ApacheAccessTraffic,
    ApacheAccessTrafficError,
    TrafficNotFoundError,
    TrafficReadError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(PROJECT_ROOT / ".env")


class ApacheAccessTrafficService:
    """設定されたApacheログから期間内の通信件数を取得する。"""

    def __init__(self, log_globs: tuple[str, ...]):
        self.log_globs = log_globs

    @classmethod
    def from_environment(cls) -> "ApacheAccessTrafficService":
        """プロジェクトの環境設定からログ検索パターンを作る。"""
        log_globs = tuple(
            value.strip()
            for value in os.getenv(
                "APACHE_ACCESS_LOG_GLOBS", "/var/log/apache2/access.log*"
            ).split(",")
            if value.strip()
        )
        return cls(log_globs=log_globs)

    def generate(
        self, period_start: datetime, period_end: datetime
    ) -> ApacheAccessTraffic:
        """指定期間の日別・応答区分別件数を保存せずに返す。"""
        paths = self._log_paths()
        try:
            traffic = ApacheAccessLogAggregator().aggregate_traffic(
                paths, period_start, period_end
            )
        except (OSError, EOFError, zlib.error) as error:
            raise TrafficReadError(
                "Apacheアクセスログを読み取れませんでした。"
            ) from error
        if traffic.total_requests == 0 and traffic.malformed_lines:
            raise ApacheAccessTrafficError("Apacheログ形式を解析できません。")
        return traffic

    def _log_paths(self) -> list[Path]:
        """設定された検索パターンに一致する重複のないログパスを返す。"""
        paths = sorted(
            {Path(name) for pattern in self.log_globs for name in glob(pattern)}
        )
        if not paths:
            raise TrafficNotFoundError(
                "Apacheアクセスログが見つかりません。設定と読み取り権限を確認してください。"
            )
        return paths
