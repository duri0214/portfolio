import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "六戸町の会議録PDFを一括ダウンロードします"

    def add_arguments(self, parser):
        parser.add_argument(
            "--save-dir",
            default=None,
            help="PDFの保存先ディレクトリ。未指定時は media/jp_stocks/rokunohe_pdf_backnumbers に保存します。",
        )
        parser.add_argument(
            "--delay",
            default=2.0,
            type=float,
            help="外部サイトへのリクエスト間隔秒数。未指定時は2秒待機します。",
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
            self.stdout.write(f"ディレクトリを作成しました: {save_dir}")

        lock_path = save_dir / ".rokunohe_pdf_download.lock"
        self._create_lock(lock_path)

        try:
            downloaded_filenames = set()
            request_count = 0

            for target_url in target_urls:
                self.stdout.write(f"処理中: {target_url}")
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

                    # PDFへのリンクを探す
                    # 六戸町のサイトでは [PDF：...KB] というテキストが含まれるリンクが多い
                    links = soup.find_all("a")

                    pdf_count = 0
                    for link in links:
                        href = link.get("href")
                        if not href:
                            continue

                        # URLに .pdf が含まれるか、リンクテキストに [PDF という文字列が含まれる場合
                        text = link.get_text()
                        if ".pdf" in href.lower() or "[pdf" in text.lower():
                            pdf_url = urljoin(self._get_base_url(target_url), href)

                            # ファイル名を取得
                            filename = self._get_filename(text=text, href=href)
                            if not filename.lower().endswith(".pdf"):
                                filename += ".pdf"

                            if filename in downloaded_filenames:
                                filename = self._get_unique_filename(
                                    filename=filename,
                                    downloaded_filenames=downloaded_filenames,
                                )

                            # 保存パス
                            save_path = save_dir / filename
                            if save_path.exists():
                                downloaded_filenames.add(filename)
                                self.stdout.write(f"スキップ (保存済み): {save_path}")
                                continue

                            # ダウンロード
                            self.stdout.write(f"ダウンロード中: {pdf_url}")
                            pdf_response, request_count = self._get_with_delay(
                                url=pdf_url,
                                delay_seconds=options["delay"],
                                request_count=request_count,
                            )
                            pdf_response.raise_for_status()

                            with open(save_path, "wb") as f:
                                f.write(pdf_response.content)

                            downloaded_filenames.add(filename)
                            pdf_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f"保存完了: {save_path}")
                            )

                    self.stdout.write(f"合計 {pdf_count} 件のPDFを処理しました。")

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"エラーが発生しました ({target_url}): {e}")
                    )
        finally:
            lock_path.unlink(missing_ok=True)

    def _get_save_dir(self, save_dir: str | None) -> Path:
        if save_dir:
            return Path(save_dir)
        return Path(settings.MEDIA_ROOT) / "jp_stocks" / "rokunohe_pdf_backnumbers"

    def _get_base_url(self, target_url: str) -> str:
        if target_url.endswith("/") or target_url.endswith(".html"):
            return target_url
        return f"{target_url}/"

    def _get_filename(self, text: str, href: str) -> str:
        filename = re.sub(r"\[pdf.*?\]", "", text, flags=re.IGNORECASE).strip()
        filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
        filename = re.sub(r"\s+", "_", filename)
        if filename:
            return filename
        return Path(href).name

    def _get_unique_filename(
        self, filename: str, downloaded_filenames: set[str]
    ) -> str:
        path = Path(filename)
        stem = path.stem
        suffix = path.suffix
        number = 2
        unique_filename = f"{stem}_{number}{suffix}"
        while unique_filename in downloaded_filenames:
            number += 1
            unique_filename = f"{stem}_{number}{suffix}"
        return unique_filename

    def _get_with_delay(
        self, url: str, delay_seconds: float, request_count: int
    ) -> tuple[requests.Response, int]:
        if request_count > 0 and delay_seconds > 0:
            time.sleep(delay_seconds)
        return requests.get(url, timeout=30), request_count + 1

    def _create_lock(self, lock_path: Path) -> None:
        try:
            with open(lock_path, "x", encoding="utf-8") as f:
                f.write("running")
        except FileExistsError as e:
            raise CommandError("六戸町PDFダウンロードは既に実行中です。") from e
