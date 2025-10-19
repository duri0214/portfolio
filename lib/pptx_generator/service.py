from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import textwrap

from lib.pptx_generator.factory import ShapeOperationFactory, TableOp, TextOp
from lib.pptx_generator.valueobject import (
    Namespaces,
    SlideLocation,
    TextContent,
    HtmlTextExtractor,
    BulletList,
    TableRecord,
    Table,
    MarkdownSection,
    BulletStyle,
    ShapeNameResolver,
)


@dataclass
class PptxToxicService:
    """PPTX のテキスト／表の置換を行うアプリケーションサービス。

    役割:
    - 値オブジェクト（Namespaces, SlideLocation, TextContent）を調整し、
      呼び出し側から XML の詳細（ネームスペース、スライドのZIP内パス、図形内部構造）を隠蔽します。

    設計意図:
    - ドメインロジック（何を置換したいか）はサービスに、XML具体操作は Value Object に切り出して責務分離。
    - 例外や入力検証はここで行い、XMLノード加工の手触りは Value Object に委譲します。

    注意点:
    - テキスト置換は最初の <a:t> ランのみ。複数ランや段落対応が必要なら TextContent を拡張してください。
    - 表は <a:tbl> または <p:tbl>（通常は p:graphicFrame 配下）を対象に、既存表を直接置換します。画像（<p:pic>）は対象外。
    - スライド番号は 1 始まり。0 以下が来た場合は SlideLocation 側で slide1.xml にフォールバックします。
    """

    @staticmethod
    def apply(
        template_pptx: Path,
        output_pptx: Path,
        source: MarkdownSection,
        page: int = 1,
        shape_name_map: dict[str, str] | None = None,
    ) -> None:
        """MarkdownSection の内容を指定された図形名へ反映します。

        - テキストはテキストボックス（<p:sp>）に反映します。
        - 表はテキスト化せず、既存の PPTX 表（a:tbl / p:tbl）を直接置換します（ヘッダ行を雛形としてデータ行を増減）。
        - 指定された図形が見つからない場合は警告のみで処理継続します。
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

        # PPTX（zip）をメモリに読み込む
        with ZipFile(str(template_pptx), "r") as input_zip:
            zip_contents = {
                item.filename: input_zip.read(item.filename)
                for item in input_zip.infolist()
            }

        # スライドの XML を解析する
        x_path = slide_loc.x_path
        if x_path not in zip_contents:
            raise KeyError(f"スライドが見つかりません: {x_path}")
        root = etree.fromstring(zip_contents[x_path])

        # テンプレート依存のマジック文字列を避けるため、図形名のマッピングは呼び出し側から必ず渡す
        if not shape_name_map:
            raise ValueError(
                "図形名マッピング(shape_name_map)が未指定です。テンプレートの図形名に合わせたマッピングを呼び出し側から渡してください。"
            )
        mapping = dict(shape_name_map)

        # ソース（MarkdownSection）からファクトリで操作一覧を生成する
        operations = ShapeOperationFactory.build(source)

        # Value Object を用いた堅牢な名前解決で図形へ適用する
        all_shapes = list(root.findall(".//p:sp", namespaces=ns.mapping))
        resolver = ShapeNameResolver(all_shapes, ns)

        has_changed = False

        # 表とテキストの振る舞いを保ちつつ、単一パスで全操作を処理する
        # 候補となる図形ノードを収集し、解決器を用意する
        candidates = list(root.findall(".//p:sp", namespaces=ns.mapping)) + list(
            root.findall(".//p:graphicFrame", namespaces=ns.mapping)
        )
        resolver_tbl = ShapeNameResolver(candidates, ns)

        for op in operations:
            shape_name_value = mapping.get(op.name_key)
            if not shape_name_value:
                continue

            if isinstance(op, TableOp):
                table_vo = op.table
                if resolver_tbl.apply_table_op(shape_name_value, table_vo, ns):
                    has_changed = True

            elif isinstance(op, TextOp):
                # テキストの描画。箇条書きは既存のスタイルを維持するため特別に処理する
                text_value = op.text
                if (
                    op.name_key == "bullet_list"
                    and source.bullet_list
                    and source.bullet_list.items
                ):
                    bullets = BulletStyle()
                    text_value = bullets.render(source.bullet_list.items)
                txt = TextContent(text_value)

                if resolver.apply_text_op(shape_name_value, txt, ns, op.name_key):
                    has_changed = True

        # 変更があった場合のみ書き戻す
        if has_changed:
            zip_contents[x_path] = etree.tostring(
                root, xml_declaration=True, encoding="utf-8"
            )

        # 新しい PPTX として保存する
        with ZipFile(str(output_pptx), "w") as output_zip:
            for filename, data in zip_contents.items():
                output_zip.writestr(filename, data)

        if not has_changed:
            print("⚠️ 反映対象が無く、PPTX の内容は変更されませんでした。")

        return None

    @staticmethod
    def _md_to_html(md_text: str) -> str:
        """Markdown 文字列を HTML に変換する（table 有効）。"""
        parser = MarkdownIt("commonmark").enable("table")
        return parser.render(md_text)

    @staticmethod
    def parse_markdown(text: str) -> MarkdownSection:
        """Markdown 文字列を解析し、見出し・段落・箇条書き・表を抽出して返す。"""
        clean_text = textwrap.dedent(text).strip()
        html = PptxToxicService._md_to_html(clean_text)

        soup = BeautifulSoup(html, "html.parser")

        # タイトル: 最初に見つかった h1〜h6 の見出しを採用
        title = None
        for level in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            elem = soup.find(level)
            if elem:
                title = elem.get_text(strip=True)
                break

        extractor = HtmlTextExtractor()

        # 段落: リストや表の外側にある上位レベルの段落のみを対象
        paragraphs: list[str] = extractor.extract_all(
            p for p in soup.find_all("p") if not p.find_parent(["li", "table"])
        )

        # 箇条書き: 表の外にある最初のリスト（ul/ol）のみを対象
        bullet_list: BulletList | None = None
        lst = soup.find(
            lambda tag: tag.name in ["ul", "ol"] and not tag.find_parent("table")
        )
        if lst:
            items = extractor.extract_all(lst.find_all("li", recursive=False))
            if not items:
                items = extractor.extract_all(lst.find_all("li"))
            if items:
                bullet_list = BulletList(items=items)

        # 表: 最初に見つかった表のみを対象
        table: Table | None = None
        tbl = soup.find("table")
        if tbl:
            records: list[TableRecord] = []
            for tr in tbl.find_all("tr"):
                cells = tr.find_all(["th", "td"])
                row = extractor.extract_all(cells)
                if row:
                    records.append(TableRecord(cells=row))
            if records:
                table = Table(records=records)

        return MarkdownSection(
            title=title, paragraphs=paragraphs, bullet_list=bullet_list, table=table
        )
