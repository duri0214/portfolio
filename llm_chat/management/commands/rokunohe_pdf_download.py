import re
import time
from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from llm_chat.domain.service.completion.rokunohe_minutes import (
    RokunoheMinutesPdfImportService,
)
from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    ROKUNOHE_MINUTES_MEDIA_DIR,
    RokunoheMinutesImportStatus,
)


class Command(BaseCommand):
    help = "六戸町の会議録PDFを一括ダウンロードし、Chroma DBにインポートします"

    def add_arguments(self, parser):
        parser.add_argument(
            "--save-dir",
            default=None,
            help="PDFの保存先ディレクトリ。未指定時は media/llm_chat/rokunohe_pdf_back_numbers に保存します。",
        )
        parser.add_argument(
            "--delay",
            default=2.0,
            type=float,
            help="外部サイトへのリクエスト間隔秒数。未指定時は2秒待機します。",
        )
        parser.add_argument(
            "--skip-import",
            action="store_true",
            help="Chroma DB へのインポートをスキップします。",
        )
        parser.add_argument(
            "--recent-days",
            default=365,
            type=int,
            help="取り込み対象にする直近日数。未指定時は365日です。",
        )

    def handle(self, *args, **options):
        # 現行ページとバックナンバーページのURL
        target_urls = [
            "https://www.town.rokunohe.aomori.jp/docs/2023051900005/",
            "https://www.town.rokunohe.aomori.jp/docs/2023051900005/chousei_cyougikai_kaigiroku_kako.html",
        ]

        # 保存先ディレクトリ
        save_dir = self._get_save_dir(options["save_dir"])
        if not save_dir.exists():
            save_dir.mkdir(parents=True)
            self._write_info(f"ディレクトリを作成しました: {save_dir}")

        lock_path = save_dir / ".rokunohe_pdf_download.lock"
        self._create_lock(lock_path)

        try:
            downloaded_filenames = set()
            request_count = 0
            source_date_from = self._get_source_date_from(options["recent_days"])
            self._write_info(
                f"六戸町PDFダウンロード開始: 保存先={save_dir}, リクエスト間隔={options['delay']}秒, source_date_from={source_date_from}"
            )

            for target_url in target_urls:
                self._write_info(f"HTML取得中: {target_url}")
                try:
                    response, request_count = self._get_with_delay(
                        url=target_url,
                        delay_seconds=options["delay"],
                        request_count=request_count,
                    )
                    response.raise_for_status()
                    # エンコーディングを自動検出（Shift_JISなどの場合があるため）
                    response.encoding = response.apparent_encoding

                    soup = BeautifulSoup(response.text, "html.parser")

                    # 六戸町のサイトでは [PDF：...KB] というテキストが含まれるリンクが多い
                    links = soup.find_all("a")
                    pdf_links = self._find_pdf_links(
                        links=links,
                        target_url=target_url,
                    )
                    self._write_info(
                        f"PDFリンク検出: {target_url} から {len(pdf_links)} 件"
                    )

                    downloaded_count = 0
                    skipped_count = 0
                    for index, pdf_link in enumerate(pdf_links, start=1):
                        filename = pdf_link["filename"]
                        if filename in downloaded_filenames:
                            filename = self._get_unique_filename(
                                filename=filename,
                                downloaded_filenames=downloaded_filenames,
                            )

                        existing_dated_path = self._get_existing_dated_path(
                            save_dir=save_dir,
                            filename=filename,
                        )

                        save_path = None
                        if existing_dated_path:
                            downloaded_filenames.add(filename)
                            if self._is_old_source(
                                existing_dated_path.name, source_date_from
                            ):
                                skipped_count += 1
                                self._write_info(
                                    f"進捗 {index}/{len(pdf_links)}: スキップ (直近1年外): {existing_dated_path}"
                                )
                                continue

                            skipped_count += 1
                            self._write_info(
                                f"進捗 {index}/{len(pdf_links)}: スキップ (保存済み): {existing_dated_path}"
                            )
                            save_path = existing_dated_path
                        else:
                            self._write_info(
                                f"進捗 {index}/{len(pdf_links)}: ダウンロード中: {pdf_link['url']}"
                            )
                            pdf_response, request_count = self._get_with_delay(
                                url=pdf_link["url"],
                                delay_seconds=options["delay"],
                                request_count=request_count,
                            )
                            pdf_response.raise_for_status()

                            filename = self._prepend_last_modified_date(
                                filename=filename,
                                response=pdf_response,
                            )
                            if self._is_old_source(filename, source_date_from):
                                skipped_count += 1
                                downloaded_filenames.add(filename)
                                self._write_info(
                                    f"進捗 {index}/{len(pdf_links)}: スキップ (直近1年外): {filename}"
                                )
                                continue

                            save_path = save_dir / filename
                            if save_path.exists():
                                skipped_count += 1
                                downloaded_filenames.add(filename)
                                self._write_info(
                                    f"進捗 {index}/{len(pdf_links)}: スキップ (保存済み): {save_path}"
                                )
                            else:
                                with open(save_path, "wb") as f:
                                    f.write(pdf_response.content)
                                downloaded_filenames.add(filename)
                                downloaded_count += 1
                                self._write_success(f"保存完了: {save_path}")

                        # Chroma DB へのインポート
                        if save_path and not options["skip_import"]:
                            self._import_to_chroma(save_path, options["recent_days"])

                    self._write_info(
                        f"処理完了: ダウンロード {downloaded_count} 件, スキップ {skipped_count} 件"
                    )

                except Exception as e:
                    self._write_error(f"エラーが発生しました ({target_url}): {e}")
            self._write_info("六戸町PDFダウンロード終了")
        finally:
            lock_path.unlink(missing_ok=True)

    @staticmethod
    def _get_save_dir(save_dir: str | None) -> Path:
        if save_dir:
            return Path(save_dir)
        return Path(settings.MEDIA_ROOT) / ROKUNOHE_MINUTES_MEDIA_DIR

    @staticmethod
    def _get_base_url(target_url: str) -> str:
        if target_url.endswith("/") or target_url.endswith(".html"):
            return target_url
        return f"{target_url}/"

    @staticmethod
    def _get_filename(text: str, href: str) -> str:
        filename = re.sub(r"\[pdf.*?]", "", text, flags=re.IGNORECASE).strip()
        filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
        filename = re.sub(r"\s+", "_", filename)
        if filename:
            return filename
        return Path(href).name

    @staticmethod
    def _get_unique_filename(filename: str, downloaded_filenames: set[str]) -> str:
        path = Path(filename)
        stem = path.stem
        suffix = path.suffix
        number = 2
        unique_filename = f"{stem}_{number}{suffix}"
        while unique_filename in downloaded_filenames:
            number += 1
            unique_filename = f"{stem}_{number}{suffix}"
        return unique_filename

    @staticmethod
    def _get_with_delay(
        url: str, delay_seconds: float, request_count: int
    ) -> tuple[requests.Response, int]:
        if request_count > 0 and delay_seconds > 0:
            time.sleep(delay_seconds)
        return requests.get(url, timeout=30), request_count + 1

    @staticmethod
    def _create_lock(lock_path: Path) -> None:
        try:
            with open(lock_path, "x", encoding="utf-8") as f:
                f.write("running")
        except FileExistsError as e:
            raise CommandError("六戸町PDFダウンロードは既に実行中です。") from e

    @staticmethod
    def _prepend_last_modified_date(filename: str, response: requests.Response) -> str:
        last_modified = response.headers.get("Last-Modified")
        if not last_modified:
            return filename

        try:
            updated_date = parsedate_to_datetime(last_modified).strftime("%Y%m%d")
        except (TypeError, ValueError, IndexError, OverflowError):
            return filename

        if filename.startswith(f"{updated_date}_"):
            return filename
        return f"{updated_date}_{filename}"

    @staticmethod
    def _get_existing_dated_path(save_dir: Path, filename: str) -> Path | None:
        dated_filename_pattern = re.compile(rf"^\d{{8}}_{re.escape(filename)}$")
        for path in save_dir.glob(f"*_{filename}"):
            if dated_filename_pattern.match(path.name):
                return path
        return None

    @staticmethod
    def _get_source_date_from(recent_days: int) -> int:
        recent_start = timezone.localdate() - timedelta(days=recent_days)
        return int(recent_start.strftime("%Y%m%d"))

    @staticmethod
    def _is_old_source(filename: str, source_date_from: int) -> bool:
        source_date = Command._get_source_date_int(filename)
        return source_date is not None and source_date < source_date_from

    @staticmethod
    def _get_source_date_int(filename: str) -> int | None:
        match = re.match(r"^(?P<date>\d{8})_", filename)
        if not match:
            return None
        return int(match.group("date"))

    @staticmethod
    def _find_pdf_links(links, target_url: str) -> list[dict[str, str]]:
        pdf_links = []
        for link in links:
            href = link.get("href")
            if not href:
                continue

            text = link.get_text()
            if ".pdf" not in href.lower() and "[pdf" not in text.lower():
                continue

            filename = Command._get_filename(text=text, href=href)
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"

            pdf_links.append(
                {
                    "filename": filename,
                    "url": urljoin(Command._get_base_url(target_url), href),
                }
            )
        return pdf_links

    def _write_info(self, message: str) -> None:
        self.stdout.write(message)

    def _write_success(self, message: str) -> None:
        self.stdout.write(self.style.SUCCESS(message))

    def _write_error(self, message: str) -> None:
        self.stdout.write(self.style.ERROR(message))

    def _import_to_chroma(self, pdf_path: Path, recent_days: int) -> None:
        """PDFからテキストを抽出し、Chroma DBにインポートします。"""
        try:
            import_service = RokunoheMinutesPdfImportService(recent_days=recent_days)
            status = import_service.import_pdf(pdf_path)
            if status == RokunoheMinutesImportStatus.SKIPPED_EXISTING:
                self._write_info(f"インポートスキップ (登録済み): {pdf_path.name}")
                return
            if status == RokunoheMinutesImportStatus.SKIPPED_OLD_SOURCE:
                self._write_info(f"インポートスキップ (直近1年外): {pdf_path.name}")
                return
            if status == RokunoheMinutesImportStatus.SKIPPED_EMPTY_TEXT:
                self._write_error(f"テキストが抽出できませんでした: {pdf_path.name}")
                return

            self._write_success(f"インポート完了: {pdf_path.name}")

        except Exception as e:
            self._write_error(f"インポートエラー ({pdf_path.name}): {e}")
