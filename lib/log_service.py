import inspect
import logging
import os
from pathlib import Path


class LogService:
    """
    ログ出力を行うサービスクラス

    このクラスはファイルへのログ出力機能を提供します。
    呼び出し元のスクリプトファイル名を自動的に取得し、ログの識別子として使用します。

    Features:
        - ファイルへのログ出力
        - 呼び出し元ファイル名の自動取得
        - UTF-8エンコーディング対応
        - タイムスタンプ付きログフォーマット

    Usage:
        log_service = LogService("./result.log")
        log_service.write("処理が完了しました")

    Notes:
        以前はコンソールとファイルの両方に出力していましたが、
        重複出力を避けるためファイルのみに出力するよう変更されました。
    """

    _FORMAT = "[%(asctime)s] in %(name)s: %(message)s"

    def __init__(self, log_file_name: str = "UNNAMED_LOG_FILE.log"):
        """
        LogServiceインスタンスを初期化します

        Args:
            log_file_name (str): ログファイルのパス。デフォルトは"UNNAMED_LOG_FILE.log"

        Notes:
            呼び出し元スクリプトのファイル名を自動的に取得し、
            ログの識別子として使用します。
        """
        # __name__の部分を呼び出し元スクリプトのファイル名に置き換えます。
        caller_file_name = inspect.stack()[1].filename
        file_name = os.path.basename(caller_file_name)
        self.logger = logging.getLogger(file_name)
        self.logger.setLevel(logging.INFO)

        # 呼び出し元のディレクトリをベースにログファイルパスを設定
        self.base_dir = Path(caller_file_name).resolve().parent
        log_path = self.base_dir / log_file_name
        self._setup_file_handler(log_path)

    def _setup_file_handler(self, log_file_name: Path):
        """
        ファイルハンドラーを設定します

        Args:
            log_file_name (Path): ログファイルのパス

        Notes:
            UTF-8エンコーディングでログファイルを作成し、
            タイムスタンプとファイル名を含むフォーマットでログを出力します。
        """
        file_handler = logging.FileHandler(log_file_name, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(self._FORMAT))
        self.logger.addHandler(file_handler)

    def write(self, message: str):
        """
        ログメッセージを出力します

        Args:
            message (str): 出力するログメッセージ

        Notes:
            ログレベルはINFOで出力されます。
            メッセージはファイルのみに出力され、コンソールには出力されません。
        """
        self.logger.info(message)
