from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import textwrap

from lib.pptx_generator.valueobject import (
    Namespaces,
    SlideLocation,
    ShapeName,
    TextContent,
    HtmlTextExtractor,
    BulletList,
    TableRecord,
    Table,
    MarkdownSection,
)


# ---------------- PPTX Services ----------------


@dataclass
class PptxTextReplaceService:
    """PPTX のテキスト置換を行うアプリケーションサービス。

    役割:
    - 値オブジェクト（Namespaces, SlideLocation, ShapeName, TextContent）を調整し、
      呼び出し側から XML の詳細（ネームスペース、スライドのZIP内パス、図形内部構造）を隠蔽します。

    設計意図:
    - ドメインロジック（何を置換したいか）はサービスに、XML具体操作は Value Object に切り出して責務分離。
    - 例外や入力検証はここで行い、XMLノード加工の手触りは Value Object に委譲します。

    注意点:
    - テキスト置換は最初の <a:t> ランのみ。複数ランや段落対応が必要なら TextContent を拡張してください。
    - 画像や表などの図形（<p:pic> 等）は対象外。現在は <p:sp> テキストボックスのみをスキャンしています。
    - スライド番号は 1 始まり。0 以下が来た場合は SlideLocation 側で slide1.xml にフォールバックします。
    """

    @staticmethod
    def replace_textbox_by_name(
        template_pptx: Path,
        output_pptx: Path,
        target_shape_name: str,
        new_text: str,
        page: int = 1,
    ) -> None:
        """指定スライド上で、図形名に一致するテキストボックスの文字列を置換します。

        要点:
        - 最初に見つかった <a:t>（テキストラン）のみを置換対象とします。
        - スライド番号は 1 始まりです。

        パラメータ:
        - template_pptx: 入力テンプレート PPTX のパス。
        - output_pptx: 出力先 PPTX のパス（親フォルダは既存である必要あり）。
        - target_shape_name: 置換対象図形（テキストボックス）の cNvPr@name。
        - new_text: 置換後の文字列。
        - page: 対象スライド番号（1 始まり）。

        戻り値:
        - なし。

        例外:
        - FileNotFoundError: テンプレート PPTX または出力フォルダが存在しない。
        - KeyError: 対象スライドが ZIP 内に存在しない。
        """
        if not template_pptx.exists():
            raise FileNotFoundError(
                f"テンプレート PPTX が見つかりません: {template_pptx}"
            )
        if not output_pptx.parent.exists():
            raise FileNotFoundError(
                f"出力フォルダが見つかりません: {output_pptx.parent}"
            )

        ns = Namespaces()
        slide_loc = SlideLocation(page)
        shape_name = ShapeName(target_shape_name)
        text_content = TextContent(new_text)

        # Load pptx (zip) to memory
        with ZipFile(str(template_pptx), "r") as input_zip:
            zip_contents = {
                item.filename: input_zip.read(item.filename)
                for item in input_zip.infolist()
            }

        # Parse slide xml
        x_path = slide_loc.x_path
        if x_path not in zip_contents:
            raise KeyError(f"スライドが見つかりません: {x_path}")
        root = etree.fromstring(zip_contents[x_path])

        # Find and replace
        replaced_any = False
        for sp in root.findall(".//p:sp", namespaces=ns.mapping):
            if shape_name.matches(sp, ns):
                text_content.apply_to_shape(sp, ns)
                replaced_any = True

        # Write back only if the replacement happened
        if replaced_any:
            zip_contents[x_path] = etree.tostring(
                root, xml_declaration=True, encoding="utf-8"
            )

        # Save as new pptx
        with ZipFile(str(output_pptx), "w") as output_zip:
            for filename, data in zip_contents.items():
                output_zip.writestr(filename, data)

        # 置換が一つも発生しなかった場合はコンソールに通知
        if not replaced_any:
            print(
                f"⚠️ 対象 '{target_shape_name}' が見つからず、置換は行われませんでした。"
            )

        return None


# ---------------- Markdown Services ----------------


def _md_to_html(md_text: str) -> str:
    """Markdown 文字列を HTML に変換する（table 有効）。"""
    parser = MarkdownIt("commonmark").enable("table")
    return parser.render(md_text)


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

    extractor = HtmlTextExtractor()

    # Paragraphs: top-level-ish paragraphs (not nested in li or table)
    paragraphs: list[str] = extractor.extract_all(
        p for p in soup.find_all("p") if not p.find_parent(["li", "table"])
    )

    # Bullet list: only the first list (ul/ol) outside tables
    bullet_list: BulletList | None = None
    for lst in soup.find_all(["ul", "ol"]):
        if lst.find_parent("table"):
            continue
        items = extractor.extract_all(lst.find_all("li", recursive=False))
        if not items:
            items = extractor.extract_all(lst.find_all("li"))
        if items:
            bullet_list = BulletList(items=items)
            break

    # Table: only the first table
    table: Table | None = None
    for tbl in soup.find_all("table"):
        records: list[TableRecord] = []
        for tr in tbl.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            row = extractor.extract_all(cells)
            if row:
                records.append(TableRecord(cells=row))
        if records:
            table = Table(records=records)
            break

    return MarkdownSection(
        title=title, paragraphs=paragraphs, bullet_list=bullet_list, table=table
    )
