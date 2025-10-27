import os
import unicodedata
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse


class ZipFileService:
    """
    ZIP ファイルの安全な取り扱いを提供するサービスクラス。

    提供機能:
    - アップロードされた ZIP の保存と安全な解凍（Zip Slip 対策）
    - 日本語ファイル名の復元（UTF-8 フラグ優先、非 UTF-8 は CP932 優先で復号）
    - 任意フォルダを ZIP 化してダウンロードレスポンスを生成

    注意事項:
    - 大容量の ZIP を扱う場合はメモリ使用量やディスク容量に注意してください。
    - 悪意あるエントリ（絶対パス、親ディレクトリへの脱出など）は `_is_safe_path` により展開しません。
    - 権限やシンボリックリンクの解決失敗など OS 依存の例外は、適切に伝播することがあります。
    """

    @staticmethod
    def handle_uploaded_zip(file: UploadedFile, app_name: str) -> Path:
        """
        アップロードされた ZIP を media/{app_name} に保存し、安全に解凍する。

        主なポイント:
        - 解凍先を作成: MEDIA_ROOT/{app_name}
        - ZIP を一旦 `uploaded.zip` として保存（ストリームチャンクで書き込み）
        - `_safe_extract` により、エントリ名のデコード/サニタイズ/Zip Slip 対策を行って展開
        - 日本語ファイル名は `_decode_zip_member_name` で UTF-8 フラグを優先、非 UTF-8 は CP932 優先で復元

        Args:
            file: Django の `UploadedFile`。通常は `InMemoryUploadedFile` や `TemporaryUploadedFile`。
            app_name: 展開先フォルダ名（MEDIA_ROOT 直下に作成されます）。

        Returns:
            Path: 実際に展開が行われたフォルダ（MEDIA_ROOT/{app_name}）。

        Raises:
            zipfile.BadZipFile: 入力が不正な ZIP の場合。
            OSError: ディスク I/O エラーやパス解決で OS レベルの問題が起きた場合。

        Notes:
            - 既存フォルダがあれば `exist_ok=True` で流用します。
            - 既存ファイルと同名の展開先がある場合は上書きされる可能性があります。
            - 悪意あるパス（../ を含む脱出や絶対パス）は `_is_safe_path` により展開をスキップします。
        """
        # 解凍場所の用意
        upload_folder = Path(settings.MEDIA_ROOT) / app_name
        upload_folder.mkdir(parents=True, exist_ok=True)

        # ファイルを保存
        destination_zip_path = upload_folder / "uploaded.zip"
        with destination_zip_path.open("wb+") as z:
            for chunk in file.chunks():
                z.write(chunk)

        # ファイルを解凍（安全な抽出を使用）
        with zipfile.ZipFile(destination_zip_path) as z:
            ZipFileService._safe_extract(z, upload_folder)

        return upload_folder

    @staticmethod
    def extract_zip_files(source_dir: Path, target_dir: Path):
        """
        指定ディレクトリ内のすべての ZIP を検出し、指定先へ安全に解凍する。

        Args:
            source_dir: ZIP ファイルを含むディレクトリ。
            target_dir: 展開先ディレクトリ。

        Raises:
            FileNotFoundError: `source_dir` または `target_dir` が存在しない場合。
            zipfile.BadZipFile: 不正な ZIP を検出した場合。
            OSError: 展開時のファイル I/O エラーなど。

        Notes:
            - 各エントリの展開は `_safe_extract` を使用し、Zip Slip 対策とファイル名の復元（日本語含む）を行います。
            - グロブは `*.zip` のみを対象とします（再帰検索は行いません）。
        """
        source_dir_path = Path(source_dir)
        target_dir_path = Path(target_dir)

        # Check if the source directory exists
        if not source_dir_path.exists():
            raise FileNotFoundError(f"The source directory {source_dir} does not exist")

        # Check if the target directory exists
        if not target_dir_path.exists():
            raise FileNotFoundError(f"The target directory {target_dir} does not exist")

        zip_files = source_dir_path.glob("*.zip")
        for zip_file in zip_files:
            with zipfile.ZipFile(str(zip_file), "r") as zip_f:
                ZipFileService._safe_extract(zip_f, target_dir_path)

    @staticmethod
    def create_zip_download(
        folder_path: str, filename: str = "download.zip"
    ) -> HttpResponse:
        """
        指定フォルダを ZIP 化し、Django のダウンロードレスポンスを返す。

        Args:
            folder_path: 圧縮対象となるフォルダのパス（再帰的に格納されます）。
            filename: ダウンロード時のファイル名（既定: "download.zip"）。

        Returns:
            HttpResponse: `Content-Type: application/zip` と `Content-Disposition` を付与したレスポンス。

        Notes:
            - 圧縮方式は `ZIP_DEFLATED` を使用します。
            - `os.walk` でフォルダ配下の全ファイルを相対パスで追加します。
            - ファイル数/サイズに応じてメモリ使用量が増えるため、必要に応じてストリーミング実装を検討してください。
        """
        import io

        # メモリ上でZIPファイルを作成
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, folder_path)
                    zipf.write(file_path, arc_name)

        # HTTPレスポンスを作成
        response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    @staticmethod
    def _decode_zip_member_name(info: zipfile.ZipInfo) -> str:
        """
        Zip エントリ名（ファイル/ディレクトリ名）をできるだけ正確に復元する。

        処理方針:
        - ZIP の「一般目的ビット 11 (0x800)」（UTF-8 フラグ）が立っている場合は、`zipfile` が提供する
          `info.filename` をそのまま信頼して返します（UTF-8 として正しい想定）。
        - それ以外の場合は、歴史的に日本の Windows 環境で多い CP932 相当を優先して復号（CP437→CP932）。
        - CP932 で復号に失敗した場合は、CP437→UTF-8(置換) で読める範囲だけ復元します。
        - それでもうまくいかない場合の最後のフォールバックは `info.filename` をそのまま返します。

        制限:
        - エンコーディング情報が ZIP に保存されていない古いアーカイブの場合、完全に元のバイト列を再現
          できないケースがあります（置換文字を含むなど）。
        """
        name = info.filename
        # UTF-8 flag (bit 11) が立っている場合
        if getattr(info, "flag_bits", 0) & 0x800:
            return name
        # CP437 → CP932（日本語 Windows 作成 Zip 対応）
        try:
            return name.encode("cp437").decode("cp932")
        except UnicodeError:
            pass
        # CP437 → UTF-8（置換）
        try:
            return name.encode("cp437").decode("utf-8", errors="replace")
        except UnicodeError:
            pass
        # 最後のフォールバック
        return name

    @staticmethod
    def _sanitize_member_name(name: str) -> str:
        """
        展開前にファイル/ディレクトリ名を正規化・サニタイズする。

        実施内容:
        - Unicode 正規化: NFKC で互換文字を統合し、見た目の等価性を高めます。
        - 制御文字の除去/置換: CR/LF/TAB/NUL をアンダースコアに置換します。
        - 区切り文字の統一: バックスラッシュをスラッシュに統一します。
        - 先頭の "./" を除去して相対表現を簡素化します。
        """
        name = unicodedata.normalize("NFKC", name)
        for ch in "\r\n\t\x00":
            name = name.replace(ch, "_")
        # Zip 内の区切りは '/' 固定だが、念のため '\\' も統一
        name = name.replace("\\", "/")
        if name.startswith("./"):
            name = name[2:]
        return name

    @staticmethod
    def _is_safe_path(base: Path, target: Path) -> bool:
        """
        Zip Slip 防止のため、`target` が `base` 配下に収まるかを検証する。

        方針:
        - `Path.resolve(strict=False)` を使って可能な範囲で実体パスに近づけ、パス前方一致で `base` 配下かを確認します。
        - 一部 OS 環境で `strict=False` の解決が例外を投げることがあるため（権限/リンク問題等）、
          その場合は `strict=True` 相当の解決を試みます。

        注意:
        - 絶対パスや `..` による外部脱出を検出する意図です。判定に通らない場合は展開しません。
        - シンボリックリンクを跨いだ意図しない脱出の可能性を低減しますが、完全な防止は OS 設定に依存します。
        """
        try:
            base_resolved = base.resolve(strict=False)
            target_resolved = (
                (base / target.name).resolve(strict=False)
                if not target.is_absolute()
                else target.resolve(strict=False)
            )
        except (OSError, RuntimeError):
            base_resolved = base.resolve()
            target_resolved = (base / target.name).resolve()
        return str(target_resolved).startswith(str(base_resolved))

    @staticmethod
    def _safe_extract(z: zipfile.ZipFile, upload_folder: Path) -> None:
        """
        エントリ名のデコード/サニタイズ/安全検証を行いながら、Zip を安全に手動抽出する。

        流れ:
        1) `z.infolist()` を走査
        2) `_decode_zip_member_name` でエントリ名を復元（UTF-8 フラグ→CP932→UTF-8(置換)）
        3) `_sanitize_member_name` で正規化・危険文字除去
        4) ディレクトリかファイルかで分岐
        5) `_is_safe_path` で Zip Slip を検出したらスキップ
        6) 問題なければディレクトリ作成後、ファイルを書き出し

        日本語ファイル名:
        - UTF-8 フラグ付きのものはそのまま展開されます。
        - フラグなしで CP932 由来と推定される場合でも、できる限りの復元を試みます。
        - 復元不能な場合は置換文字を含む名前になる場合があります。
        """
        for info in z.infolist():
            name = ZipFileService._decode_zip_member_name(info)
            name = ZipFileService._sanitize_member_name(name)

            # ディレクトリエントリの扱い
            if name.endswith("/"):
                dest_dir = upload_folder / name
                if not ZipFileService._is_safe_path(upload_folder, dest_dir):
                    continue
                dest_dir.mkdir(parents=True, exist_ok=True)
                continue

            # ファイルエントリ
            dest_path = upload_folder / name
            # 親ディレクトリの安全性も含め、ベース配下チェック
            if not ZipFileService._is_safe_path(upload_folder, dest_path.parent):
                continue
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(dest_path, "wb") as out:
                out.write(src.read())

    @staticmethod
    def _convert_to_cp932(folder_name: str) -> str:
        """
        互換ユーティリティ: CP437 ベースの文字列を CP932 として復元を試みる。

        用途:
        - 古い ZIP 等で、ファイル名が CP437 ベースで記録されている場合の暫定変換に使用できます。
        - 現行の実装では `_decode_zip_member_name` に包括されているため、通常はそちらを利用してください。

        Returns:
            str: 復元できた場合は CP932 としてデコードした文字列。失敗時は入力をそのまま返します。

        See Also:
            https://qiita.com/tohka383/items/b72970b295cbc4baf5ab
        """
        try:
            return folder_name.encode("cp437").decode("cp932")
        except (UnicodeEncodeError, UnicodeDecodeError):
            # エンコーディング変換に失敗した場合は元の文字列を返す
            return folder_name
