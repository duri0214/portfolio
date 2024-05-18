import logging


class LogService:
    _format = "[%(asctime)s] in %(module)s: %(message)s"

    def __init__(self, log_file_name: str = "./generic.log"):
        """
        Args:
            log_file_name: 出力するログのパス
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(log_file_name, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(self._format))
        self.logger.addHandler(file_handler)

    def write(self, message: str):
        logging.info(message)
        self.logger.info(message)
