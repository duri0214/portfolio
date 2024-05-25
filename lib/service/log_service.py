import logging


class LogService:
    _FORMAT = "[%(asctime)s] in %(module)s: %(message)s"

    def __init__(self, log_file_name: str = "UNNAMED_LOG_FILE.log"):
        self.logger = logging.getLogger(__name__)
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
