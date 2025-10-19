from dataclasses import dataclass
import textwrap
from typing import Iterable, cast
from bs4 import BeautifulSoup
from bs4.element import Tag, PageElement
from markdown_it import MarkdownIt


@dataclass(frozen=True)
class HtmlTextExtractor:
    """BeautifulSoup の Tag から安全にテキストを抽出する値オブジェクト。

    - separator と strip を固定し、型不整合をこの層で閉じ込める。
    - 外部からは型安全な API のみを露出する。
    """

    separator: str = " "
    strip: bool = True

    def extract_all(self, elements: Iterable[Tag]) -> list[str]:
        results: list[str] = []
        for e in elements:
            text = self.extract(e)
            if text:
                results.append(text)
        return results

    def extract(self, element: Tag) -> str:
        """BeautifulSoup.get_text の型スタブ不整合に関するエクスキューズをここに集約。
        - いくつかの bs4 の型スタブでは get_text のシグネチャが実装と食い違い、
          separator/strip をキーワード指定しても型検査で誤検出される場合がある。
        - 本実装はランタイムでは正しく動作するため、誤検出のみを抑止する目的で
          `# type: ignore[arg-type]` を最小範囲（この呼び出し行）に限定して付与している。
        - 目的は「VO 内にライブラリ依存と型差異を閉じ込め、外部には型安全な API だけを露出する」こと。
        """
        el = cast(PageElement, element)
        return el.get_text(separator=self.separator, strip=self.strip)  # type: ignore[arg-type]


def _md_to_html(md_text: str) -> str:
    """Markdown 文字列を HTML に変換する。

    実装: markdown-it-py を利用（table を有効化）。
    """
    parser = MarkdownIt("commonmark").enable("table")
    return parser.render(md_text)


@dataclass(frozen=True)
class BulletList:
    """箇条書き1セット（ul/ol）を表す値オブジェクト。

    - items: 各アイテムのテキスト。
    """

    items: list[str]


@dataclass(frozen=True)
class TableRecord:
    """表の1レコード（1行）を表す値オブジェクト。

    - cells: 各セルのテキスト。
    """

    cells: list[str]


@dataclass(frozen=True)
class Table:
    """表全体を表す値オブジェクト（先頭にヘッダ行を含む）。

    - records: 行（レコード）の配列。
    """

    records: list[TableRecord]


@dataclass(frozen=True)
class MarkdownSection:
    """Markdown の内容を中立的な構造にした値オブジェクト。

    - title: 最初に出現する見出し（h1〜h6）のテキスト。無ければ None。
    - paragraphs: 段落テキストの一覧（リストや表の中は除外）。
    - lists: 各箇条書きを BulletList として保持。
    - tables: 各表を Table として保持（先頭にヘッダ行を含む）。
    """

    title: str | None
    paragraphs: list[str]
    lists: list[BulletList]
    tables: list[Table]


def parse_markdown(text: str) -> MarkdownSection:
    """Markdown 文字列を解析し、見出し・段落・箇条書き・表を抽出して返す。"""
    clean_text = textwrap.dedent(text).strip()
    html = _md_to_html(clean_text)

    soup = BeautifulSoup(html, "html.parser")

    # Title: first heading among h1...h6
    title = None
    for level in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        elem = soup.find(level)
        if elem:
            title = elem.get_text(strip=True)
            break

    # Paragraphs: top-level-ish paragraphs (not nested in li or table)
    extractor = HtmlTextExtractor()
    paragraphs: list[str] = extractor.extract_all(
        p for p in soup.find_all("p") if not p.find_parent(["li", "table"])
    )

    # Lists: each UL/OL as a BulletList
    lists: list[BulletList] = []
    for lst in soup.find_all(["ul", "ol"]):
        # Avoid capturing list items that appear inside tables (rare in Markdown)
        if lst.find_parent("table"):
            continue
        items = extractor.extract_all(lst.find_all("li", recursive=False))
        # Fallback to a recursive collection if needed
        if not items:
            items = extractor.extract_all(lst.find_all("li"))
        if items:
            lists.append(BulletList(items=items))

    # Tables: rows and cells as Table with TableRecord
    tables: list[Table] = []
    for table in soup.find_all("table"):
        records: list[TableRecord] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            row = extractor.extract_all(cells)
            if row:
                records.append(TableRecord(cells=row))
        if records:
            tables.append(Table(records=records))

    return MarkdownSection(
        title=title, paragraphs=paragraphs, lists=lists, tables=tables
    )
