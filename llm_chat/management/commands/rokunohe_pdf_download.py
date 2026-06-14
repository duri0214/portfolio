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
    """
    六戸町公式サイトから会議録PDFを収集し、必要に応じてChroma DBへ登録する管理コマンド。

    このコマンドは、外部サイト巡回、PDF保存、期間判定、Chroma登録を一続きで扱います。
    管理画面の「会議録PDF取得・ベクトル化」ボタンからも呼ばれるため、同時実行防止、
    進捗ログ、直近1年/明示期間フィルタをここでまとめて制御します。

    処理の流れ:
    1. 現行ページとバックナンバーページからPDFリンクを抽出する。
    2. 保存済みの日付付きPDFがあれば再ダウンロードせず、そのPDFを登録候補にする。
    3. 未保存PDFはLast-Modifiedの日付をファイル名へ付与してから保存する。
    4. ファイル名の日付が対象期間外なら保存・登録をスキップする。
    5. skip-import未指定時はRokunoheMinutesPdfImportServiceへ渡してChroma DBへ登録する。
    """

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
            help="取り込み対象にする直近日数。source-date-from未指定時は365日です。",
        )
        parser.add_argument(
            "--source-date-from",
            default=None,
            type=int,
            help="取り込み対象にするPDF日付の下限。YYYYMMDD形式です。",
        )
        parser.add_argument(
            "--source-date-to",
            default=None,
            type=int,
            help="取り込み対象にするPDF日付の上限。YYYYMMDD形式です。",
        )

    def handle(self, *args, **options):
        """
        PDFリンク収集、保存済み判定、対象期間判定、Chroma登録を実行します。

        save_dir配下にロックファイルを作って並行実行を拒否し、完了時には必ず削除します。
        外部サイトへの連続アクセスを避けるため、HTML取得とPDF取得の両方で
        delayを挟みます。個別URLで例外が起きても、他の対象URLの処理は継続します。
        """
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
            source_date_from = self._get_source_date_from(
                recent_days=options["recent_days"],
                source_date_from=options["source_date_from"],
            )
            source_date_to = options["source_date_to"]
            self._validate_source_date_range(
                source_date_from=source_date_from,
                source_date_to=source_date_to,
            )
            self._write_info(
                f"六戸町PDFダウンロード開始: 保存先={save_dir}, リクエスト間隔={options['delay']}秒, source_date_from={source_date_from}, source_date_to={source_date_to or '指定なし'}"
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
                            if self._is_out_of_source_date_range(
                                filename=existing_dated_path.name,
                                source_date_from=source_date_from,
                                source_date_to=source_date_to,
                            ):
                                skipped_count += 1
                                self._write_info(
                                    f"進捗 {index}/{len(pdf_links)}: スキップ (対象期間外): {existing_dated_path}"
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
                            if self._is_out_of_source_date_range(
                                filename=filename,
                                source_date_from=source_date_from,
                                source_date_to=source_date_to,
                            ):
                                skipped_count += 1
                                downloaded_filenames.add(filename)
                                self._write_info(
                                    f"進捗 {index}/{len(pdf_links)}: スキップ (対象期間外): {filename}"
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
                            self._import_to_chroma(
                                pdf_path=save_path,
                                recent_days=options["recent_days"],
                                source_date_from=source_date_from,
                                source_date_to=source_date_to,
                            )

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
        """
        HTTP Last-ModifiedからYYYYMMDD_プレフィックス付きファイル名を作ります。

        六戸町のPDFリンクテキストだけでは日付が分からないことがあるため、
        レスポンスヘッダの日付を保存ファイル名へ埋め込みます。この日付は後続の
        直近1年/明示期間フィルタと、Chroma metadataのsource_dateになります。
        """
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
        """
        同じPDF名に日付プレフィックスが付いた保存済みファイルを探します。

        HTML上のリンク名は日付なしで取得されることがある一方、保存時には
        Last-Modified由来のYYYYMMDD_を付けます。再実行時に同じPDFを再取得しないため、
        日付付き保存名と元リンク名を対応させます。
        """
        dated_filename_pattern = re.compile(rf"^\d{{8}}_{re.escape(filename)}$")
        for path in save_dir.glob(f"*_{filename}"):
            if dated_filename_pattern.match(path.name):
                return path
        return None

    @staticmethod
    def _get_source_date_from(*, recent_days: int, source_date_from: int | None) -> int:
        """
        PDF収集対象期間の下限日付をYYYYMMDD整数で決定します。

        source-date-fromが明示された場合はその日付を使います。未指定時は
        管理画面の通常実行と同じく、今日からrecent_days日前を下限にします。
        """
        if source_date_from is not None:
            return source_date_from
        recent_start = timezone.localdate() - timedelta(days=recent_days)
        return int(recent_start.strftime("%Y%m%d"))

    @staticmethod
    def _validate_source_date_range(
        *, source_date_from: int, source_date_to: int | None
    ) -> None:
        """
        明示された処理期間が逆転していないことを検証します。

        範囲が逆転したまま外部サイトへアクセスすると、意図しない全スキップや
        分かりにくいログになるため、処理開始前にCommandErrorで止めます。
        """
        if source_date_to is not None and source_date_from > source_date_to:
            raise CommandError(
                "source-date-from は source-date-to 以下の日付を指定してください。"
            )

    @staticmethod
    def _is_out_of_source_date_range(
        *, filename: str, source_date_from: int, source_date_to: int | None
    ) -> bool:
        """
        保存ファイル名の日付がPDF収集対象期間外かを判定します。

        ファイル名にYYYYMMDD_プレフィックスがない場合は日付判定できないため
        対象期間内として扱います。日付がある場合は、下限未満または上限超過を
        対象期間外にします。
        """
        source_date = Command._get_source_date_int(filename)
        if source_date is None:
            return False
        if source_date < source_date_from:
            return True
        return source_date_to is not None and source_date > source_date_to

    @staticmethod
    def _get_source_date_int(filename: str) -> int | None:
        match = re.match(r"^(?P<date>\d{8})_", filename)
        if not match:
            return None
        return int(match.group("date"))

    @staticmethod
    def _find_pdf_links(links, target_url: str) -> list[dict[str, str]]:
        """
        HTML上のaタグ一覧から六戸町会議録PDF候補リンクを抽出します。

        六戸町ページではhrefがPDFでなくてもリンクテキストに[PDF]が含まれる場合があるため、
        hrefと表示テキストの両方を見ます。戻り値は後続の保存処理が扱いやすいよう、
        正規化済みファイル名と絶対URLのdictにします。
        """
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

    def _import_to_chroma(
        self,
        *,
        pdf_path: Path,
        recent_days: int,
        source_date_from: int,
        source_date_to: int | None,
    ) -> None:
        """
        保存済みPDFをRokunoheMinutesPdfImportServiceへ渡してChroma DBへ登録します。

        コマンド側で決定したrecent_days/source_date_from/source_date_toをServiceへ渡し、
        ダウンロード時とインポート時で同じ期間基準を使います。Serviceの戻り値ごとに
        管理画面やサーバログで読めるメッセージへ変換します。
        """
        try:
            import_service = RokunoheMinutesPdfImportService(
                recent_days=recent_days,
                source_date_from=source_date_from,
                source_date_to=source_date_to,
            )
            status = import_service.import_pdf(pdf_path)
            if status == RokunoheMinutesImportStatus.SKIPPED_EXISTING:
                self._write_info(f"インポートスキップ (登録済み): {pdf_path.name}")
                return
            if status == RokunoheMinutesImportStatus.SKIPPED_OUT_OF_SOURCE_DATE_RANGE:
                self._write_info(f"インポートスキップ (対象期間外): {pdf_path.name}")
                return
            if status == RokunoheMinutesImportStatus.SKIPPED_EMPTY_TEXT:
                self._write_error(f"テキストが抽出できませんでした: {pdf_path.name}")
                return

            self._write_success(f"インポート完了: {pdf_path.name}")

        except Exception as e:
            self._write_error(f"インポートエラー ({pdf_path.name}): {e}")
