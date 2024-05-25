from pathlib import Path
from unittest import TestCase

from lib.service.log_service import LogService


class TestLogService(TestCase):
    LOG_NAME = "abc.log"
    TEST_STRING = "abc"

    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent
        self.log_path = str(self.base_dir / self.LOG_NAME)
        self.log = LogService(self.log_path)
        with open(self.log_path, "a") as f:  # append モード
            pass  # ファイルを開いただけで何も操作は行なっていません
        with open(self.log_path) as f:
            self.initial_log_content = f.read()

    def test_write(self):
        """
        テスト実行ごとに `abc` というログを出力し、ログ出力前よりも `abc` のカウントが `1` 多いことを確認する
        """
        self.log.write(self.TEST_STRING + "日本語も大丈夫")

        with open(self.log_path) as f:
            final_log_content = f.read()

        self.assertEqual(
            self.initial_log_content.count(self.TEST_STRING) + 1,
            final_log_content.count(self.TEST_STRING),
        )
