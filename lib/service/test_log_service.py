from pathlib import Path
from unittest import TestCase

from lib.service.log_service import LogService


class TestLogService(TestCase):
    def test_write(self):
        """
        テスト実行ごとに `abc` というログを出力し、ログ出力前よりも `abc` のカウントが `1` 多いことを確認する
        """
        base_dir = Path(__file__).resolve().parent
        log_path = base_dir / "abc.log"

        log = LogService(str(log_path))
        if not log_path.is_file():
            log.write("")

        with open(log_path) as f:
            stream_in_log1 = f.read()
        log.write(Path(__file__).stem)
        log.write("abc日本語も大丈夫")
        with open(log_path) as f:
            stream_in_log2 = f.read()

        expected = stream_in_log1.count("abc") + 1
        self.assertEqual(expected, stream_in_log2.count("abc"))
