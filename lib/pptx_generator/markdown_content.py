from dataclasses import dataclass
import textwrap
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt


def _md_to_html(md_text: str) -> str:
    """Markdown 文字列を HTML に変換する。

    実装: markdown-it-py を利用（table を有効化）。
    """
    parser = MarkdownIt("commonmark").enable("table")
    return parser.render(md_text)


@dataclass(frozen=True)
class MarkdownSection:
    """Markdown の内容を中立的な構造にした値オブジェクト。

    - title: 最初に出現する見出し（h1〜h6）のテキスト。無ければ None。
    - paragraphs: 段落テキストの一覧（リストや表の中は除外）。
    - lists: 各箇条書き（ul/ol）をアイテム文字列のリストとして保持。
    - tables: 各表を 行×列 の文字列マトリクスとして保持（ヘッダ行を先頭に含む）。
    """

    title: str | None
    paragraphs: list[str]
    lists: list[list[str]]
    tables: list[list[list[str]]]


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
    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        if p.find_parent(["li", "table"]):
            continue
        txt = p.get_text(" ", True)
        if txt:
            paragraphs.append(txt)

    # Lists: each UL/OL as a list of items
    lists: list[list[str]] = []
    for lst in soup.find_all(["ul", "ol"]):
        # Avoid capturing list items that appear inside tables (rare in Markdown)
        if lst.find_parent("table"):
            continue
        items: list[str] = []
        for li in lst.find_all("li", recursive=False):
            txt = li.get_text(" ", True)
            if txt:
                items.append(txt)
        # Fallback to a recursive collection if needed
        if not items:
            for li in lst.find_all("li"):
                txt = li.get_text(" ", True)
                if txt:
                    items.append(txt)
        if items:
            lists.append(items)

    # Tables: rows and cells
    tables: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        table_rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            row: list[str] = [c.get_text(" ", True) for c in cells]
            if row:
                table_rows.append(row)
        if table_rows:
            tables.append(table_rows)

    return MarkdownSection(
        title=title, paragraphs=paragraphs, lists=lists, tables=tables
    )
