import os
from pathlib import Path
from unittest import TestCase

from vietnam_research.domain.service.logservice import LogService


class TestLogService(TestCase):
    def test_write(self):
        """
        テスト実行ごとに `abc` というログを出力し、ログ出力前よりも `abc` のカウントが `1` 多いことを確認する
        """
        log_path = f'./abc.log'

        log = LogService(log_path)
        if not os.path.isfile(log_path):
            log.write('')

        with open(log_path) as f:
            stream_in_log1 = f.read()
        log.write('abc')
        with open(log_path) as f:
            stream_in_log2 = f.read()

        expected = stream_in_log1.count('abc') + 1
        self.assertEqual(expected, stream_in_log2.count('abc'))
