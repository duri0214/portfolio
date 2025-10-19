"""Markdown→構造データ変換(parse_markdown)の回帰テスト群。

目的:
- MarkdownSection に正しくマッピングできることを、段落・箇条書き・表の観点で検証する。
- HTML 変換と BeautifulSoup 抽出の最小仕様を固定化する。

注意:
- 入力の Markdown は最小ケースを用い、余計な装飾や拡張記法は使わない。
"""

import unittest

from lib.pptx_generator.markdown_content import (
    MarkdownSection,
    parse_markdown,
)


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
        - Then: title に見出しテキスト、paragraphs に段落のみが入り、lists, tables は空。
        """
        md = """
        ## 見出しと1つの段落をテストする
        これはテストです。
        """
        section = parse_markdown(md)
        self.assertIsInstance(section, MarkdownSection)
        self.assertEqual(section.title, "見出しと1つの段落をテストする")
        self.assertEqual(section.paragraphs, ["これはテストです。"])
        self.assertEqual(section.lists, [])
        self.assertEqual(section.tables, [])

    def test_list_extraction(self):
        """シナリオ:
        - Given: 見出しと、ハイフン形式の箇条書き3項目。
        - When: 解析する。
        - Then: lists に1件のリストが入り、アイテムの前後空白や改行は正規化される。paragraphs, tables は空。
        """
        md = """
        ## 箇条書き3項目をテストする
        - 北海道: 120万円  
        - 東京: 350万円  
        - 大阪: 280万円
        """
        section = parse_markdown(md)
        self.assertEqual(section.title, "箇条書き3項目をテストする")
        self.assertEqual(section.paragraphs, [])
        self.assertEqual(len(section.lists), 1)
        self.assertEqual(
            section.lists[0].items,
            [
                "北海道: 120万円",
                "東京: 350万円",
                "大阪: 280万円",
            ],
        )
        self.assertEqual(section.tables, [])

    def test_table_extraction(self):
        md = """
        ## 表をテストする
        | 拠点 | 売上 | 前期比 |
        |------|------|--------|
        | 北海道 | 120 | +10% |
        | 東京 | 350 | +5% |
        | 大阪 | 280 | +8% |
        """
        section = parse_markdown(md)
        self.assertEqual(section.title, "表をテストする")
        self.assertEqual(section.paragraphs, [])
        self.assertEqual(section.lists, [])

        # One table expected
        self.assertEqual(len(section.tables), 1)
        table = section.tables[0]

        # Expect header + 3 rows
        self.assertEqual(table.records[0].cells, ["拠点", "売上", "前期比"])
        self.assertEqual(table.records[1].cells, ["北海道", "120", "+10%"])
        self.assertEqual(table.records[2].cells, ["東京", "350", "+5%"])
        self.assertEqual(table.records[3].cells, ["大阪", "280", "+8%"])
