import inspect
import logging
import os


class LogService:
    _FORMAT = "[%(asctime)s] in %(name)s: %(message)s"

    def __init__(self, log_file_name: str = "UNNAMED_LOG_FILE.log"):
        # __name__の部分を呼び出し元スクリプトのファイル名に置き換えます。
        caller_file_name = inspect.stack()[1].filename
        file_name = os.path.basename(caller_file_name)
        self.logger = logging.getLogger(file_name)
        self.logger.setLevel(logging.INFO)
        self._setup_file_handler(log_file_name)
        self._setup_console_handler()

    def _setup_file_handler(self, log_file_name: str):
        file_handler = logging.FileHandler(log_file_name, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(self._FORMAT))
        self.logger.addHandler(file_handler)

    def _setup_console_handler(self):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(self._FORMAT))
        self.logger.addHandler(console_handler)

    def write(self, message: str):
        self.logger.info(message)
