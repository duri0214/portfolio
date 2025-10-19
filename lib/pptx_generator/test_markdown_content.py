"""Markdown→構造データ変換(parse_markdown)の回帰テスト群。

目的:
- MarkdownSection に正しくマッピングできることを、段落・箇条書き・表の観点で検証する。
- HTML 変換と BeautifulSoup 抽出の最小仕様を固定化する。

注意:
- 入力の Markdown は最小ケースを用い、余計な装飾や拡張記法は使わない。
"""

import unittest

from lib.pptx_generator.valueobject import MarkdownSection
from lib.pptx_generator.service import PptxToxicService


class TestMarkdownContent(unittest.TestCase):
    """parse_markdown の基本シナリオを網羅するテストクラス。

    検証観点:
    - 見出しの抽出: 最初に現れる h1〜h6 が title に入る。
    - 段落の抽出: li/table 配下ではない <p> のみ paragraphs に入る。
    - 箇条書きの抽出: 各 <ul>/<ol> を 1 リストとして items 文字列の配列にする。
    - 表の抽出: <table> の行列をテキスト化し、ヘッダ行が先頭に来る。
    """

    def test_paragraph_extraction(self):
        """シナリオ:
        - Given: 見出し(h2)と1つの段落を含む Markdown。
        - When: parse_markdown に渡して解析する。
        - Then: title に見出しテキスト、paragraphs に段落のみが入り、bullet_list, table は空。
        """
        md = """
        ## 見出しと1つの段落をテストする
        これはテストです。
        """
        parsed_md = PptxToxicService.parse_markdown(md)
        self.assertIsInstance(parsed_md, MarkdownSection)
        self.assertEqual(parsed_md.title, "見出しと1つの段落をテストする")
        self.assertEqual(parsed_md.paragraphs, ["これはテストです。"])
        self.assertIsNone(parsed_md.bullet_list)
        self.assertIsNone(parsed_md.table)

    def test_list_extraction(self):
        """シナリオ:
        - Given: 見出しと、ハイフン形式の箇条書き3項目。
        - When: 解析する。
        - Then: bullet_list に1件のリストが入り、アイテムの前後空白や改行は正規化される。paragraphs, table は空。
        """
        md = """
        ## 箇条書き3項目をテストする
        - 北海道: 120万円  
        - 東京: 350万円  
        - 大阪: 280万円
        """
        parsed_md = PptxToxicService.parse_markdown(md)
        self.assertEqual(parsed_md.title, "箇条書き3項目をテストする")
        self.assertEqual(parsed_md.paragraphs, [])
        self.assertIsNotNone(parsed_md.bullet_list)
        self.assertEqual(
            parsed_md.bullet_list.items if parsed_md.bullet_list else [],
            [
                "北海道: 120万円",
                "東京: 350万円",
                "大阪: 280万円",
            ],
        )
        self.assertIsNone(parsed_md.table)

    def test_table_extraction(self):
        md = """
        ## 表をテストする
        | 拠点 | 売上 | 前期比 |
        |------|------|--------|
        | 北海道 | 120 | +10% |
        | 東京 | 350 | +5% |
        | 大阪 | 280 | +8% |
        """
        parsed_md = PptxToxicService.parse_markdown(md)
        self.assertEqual(parsed_md.title, "表をテストする")
        self.assertEqual(parsed_md.paragraphs, [])
        self.assertIsNone(parsed_md.bullet_list)

        # One table expected
        self.assertIsNotNone(parsed_md.table)
        table = parsed_md.table

        # Expect header + 3 rows
        self.assertIsNotNone(table)
        if table:
            self.assertEqual(table.records[0].cells, ["拠点", "売上", "前期比"])
            self.assertEqual(table.records[1].cells, ["北海道", "120", "+10%"])
            self.assertEqual(table.records[2].cells, ["東京", "350", "+5%"])
            self.assertEqual(table.records[3].cells, ["大阪", "280", "+8%"])
