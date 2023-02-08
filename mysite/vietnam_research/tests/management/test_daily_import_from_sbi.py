from django.test import TestCase

from vietnam_research.management.commands.daily_import_from_sbi import process_the_text


class Test(TestCase):
    def test_process_the_text(self):
        the_text = 'あ【韓国】▼指数チャート 【ベトナム】ベトナムの経済ニュース▼指数チャート2,1202,2102【インドネシア】'
        expected = '新興国ウィークリーレポート<br>ベトナムの経済ニュース2'
        self.assertEqual(expected, process_the_text(the_text))
