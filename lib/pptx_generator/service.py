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
    TextContent,
    HtmlTextExtractor,
    BulletList,
    TableRecord,
    Table,
    MarkdownSection,
)


# ---------------- PPTX Services ----------------


@dataclass
class PptxToxicService:
    """PPTX のテキスト置換を行うアプリケーションサービス。

    役割:
    - 値オブジェクト（Namespaces, SlideLocation, TextContent）を調整し、
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
    def apply(
        template_pptx: Path,
        output_pptx: Path,
        source: MarkdownSection,
        page: int = 1,
        shape_name_map: dict[str, str] | None = None,
    ) -> None:
        """MarkdownSection の内容を指定された図形名へ反映します。

        - すべてテキストボックス（<p:sp>）へのテキスト反映として実装します。
        - 表は簡易にテキスト化（行を改行、セルはタブ区切り）して流し込みます。
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

        # shape name mapping (keys: title, paragraphs, bullet_list, table)
        mapping = {
            "title": "Title",
            "paragraphs": "Paragraphs",
            "bullet_list": "BulletList",
            "table": "Table",
        }
        if shape_name_map:
            mapping.update(shape_name_map)

        # prepare rendered texts
        rendered: dict[str, str] = {}
        if source.title is not None:
            rendered["title"] = source.title
        if source.paragraphs:
            rendered["paragraphs"] = "\n\n".join(source.paragraphs)
        if source.bullet_list and source.bullet_list.items:
            rendered["bullet_list"] = "\n".join(
                f"• {it}" for it in source.bullet_list.items
            )
        # テーブルはテキストではなく、本物の PPTX 表（a:tbl/p:tbl）を操作して反映するため、
        # rendered には追加しない。

        # apply to shapes with robust matching
        # - Build an index of all shapes with their cNvPr@name
        def _shape_name(sp_el: etree.ElementBase) -> str | None:
            name_el = sp_el.find(".//p:cNvPr", namespaces=ns.mapping)
            return None if name_el is None else name_el.get("name")

        all_shapes = list(root.findall(".//p:sp", namespaces=ns.mapping))
        indexed: list[tuple[etree.ElementBase, str | None]] = [
            (sp, _shape_name(sp)) for sp in all_shapes
        ]

        def _resolve_targets(
            name_or_names: str | list[str] | tuple[str, ...],
        ) -> list[etree.ElementBase]:
            # Normalize targets list
            if isinstance(name_or_names, (list, tuple)):
                target_names = [t for t in name_or_names if isinstance(t, str) and t]
            else:
                target_names = [name_or_names] if name_or_names else []
            if not target_names:
                return []

            # Tier 1: exact match (case-sensitive)
            exact_matches = [sp for sp, nm in indexed if nm in target_names]
            if exact_matches:
                return exact_matches

            # Tier 2: exact match (case-insensitive)
            targets_lower = {t.lower() for t in target_names}
            exact_ci_matches = [
                sp
                for sp, nm in indexed
                if isinstance(nm, str) and nm.lower() in targets_lower
            ]
            if exact_ci_matches:
                return exact_ci_matches

            # Tier 3: substring match (case-insensitive)
            substr_matches = []
            for sp, nm in indexed:
                if not isinstance(nm, str):
                    continue
                nm_l = nm.lower()
                for t in targets_lower:
                    if t and t in nm_l:
                        substr_matches.append(sp)
                        break
            return substr_matches

        replaced_any = False

        # --- Table replacement: operate on real PPTX tables (a:tbl / p:tbl) ---
        if source.table and source.table.records:
            shape_name_value = mapping.get("table")
            if shape_name_value:
                # Collect candidate containers: text shapes and graphic frames
                candidates = list(
                    root.findall(".//p:sp", namespaces=ns.mapping)
                ) + list(root.findall(".//p:graphicFrame", namespaces=ns.mapping))

                def _name_of(el: etree.ElementBase) -> str | None:
                    nm = el.find(".//p:cNvPr", namespaces=ns.mapping)
                    return None if nm is None else nm.get("name")

                indexed_tbl: list[tuple[etree.ElementBase, str | None]] = [
                    (el, _name_of(el)) for el in candidates
                ]

                # Resolve targets by name (exact, case-insensitive, then substring)
                if isinstance(shape_name_value, (list, tuple)):
                    targets_raw = [
                        t for t in shape_name_value if isinstance(t, str) and t
                    ]
                else:
                    targets_raw = [shape_name_value] if shape_name_value else []

                targets: list[etree.ElementBase] = []
                if targets_raw:
                    exact = [el for el, nm in indexed_tbl if nm in targets_raw]
                    targets = exact
                    if not targets:
                        t_lower = {t.lower() for t in targets_raw}
                        exact_ci = [
                            el
                            for el, nm in indexed_tbl
                            if isinstance(nm, str) and nm.lower() in t_lower
                        ]
                        targets = exact_ci
                    if not targets:
                        subs: list[etree.ElementBase] = []
                        t_lower = {t.lower() for t in targets_raw}
                        for el, nm in indexed_tbl:
                            if not isinstance(nm, str):
                                continue
                            nl = nm.lower()
                            for t in t_lower:
                                if t and t in nl:
                                    subs.append(el)
                                    break
                        targets = subs

                if targets:
                    found_any_tbl = False
                    for el in targets:
                        tbl_el = el.find(".//a:tbl", namespaces=ns.mapping)
                        if tbl_el is None:
                            tbl_el = el.find(".//p:tbl", namespaces=ns.mapping)
                        if tbl_el is not None:
                            PptxToxicService.replace_table(tbl_el, source.table, ns)
                            replaced_any = True
                            found_any_tbl = True
                    if not found_any_tbl:
                        print(
                            f"⚠️ 指定図形 '{shape_name_value}' は見つかったが、表 (a:tbl/p:tbl) が見つかりませんでした。"
                        )
                else:
                    # diagnostics for available names
                    available_names = [
                        nm for _, nm in indexed_tbl if isinstance(nm, str)
                    ]
                    preview = ", ".join(available_names[:10])
                    more = (
                        ""
                        if len(available_names) <= 10
                        else f" 他 {len(available_names) - 10} 件"
                    )
                    print(
                        f"⚠️ 指定された表図形 '{shape_name_value}' が見つかりませんでした。候補: {preview}{more}"
                    )

        for key, text in rendered.items():
            shape_name_value = mapping.get(key)
            if not shape_name_value:
                continue
            txt = TextContent(text)
            targets = _resolve_targets(shape_name_value)
            if targets:
                for sp in targets:
                    txt.apply_to_shape(sp, ns)
                    replaced_any = True
            else:
                # prepare available names for diagnostics
                available_names = [nm for _, nm in indexed if isinstance(nm, str)]
                preview = ", ".join(available_names[:10])
                more = (
                    ""
                    if len(available_names) <= 10
                    else f" 他 {len(available_names) - 10} 件"
                )
                print(
                    f"⚠️ 指定された図形 '{shape_name_value}'（{key}）が見つかりませんでした。候補: {preview}{more}"
                )

        # Write back only if something changed
        if replaced_any:
            zip_contents[x_path] = etree.tostring(
                root, xml_declaration=True, encoding="utf-8"
            )

        # Save as new pptx
        with ZipFile(str(output_pptx), "w") as output_zip:
            for filename, data in zip_contents.items():
                output_zip.writestr(filename, data)

        if not replaced_any:
            print("⚠️ 反映対象が無く、PPTX の内容は変更されませんでした。")

        return None

    @staticmethod
    def replace_table(tbl_el: etree.ElementBase, table: Table, ns: Namespaces) -> None:
        """
        既存の PPTX 表 (a:tbl / p:tbl) を Markdown の Table で置換する。
        - 先頭行（ヘッダ行）はテンプレートのまま残し、以降の行は削除して Markdown レコードで再構築。
        - 各データ行はヘッダ行のスタイルをコピーして作成。
        - 列数が一致しない場合は、短い方に合わせて切り詰めます。
        """
        # 既存行（a:tr）取得
        tr_list = tbl_el.findall("./a:tr", namespaces=ns.mapping)
        if not tr_list:
            # 一部テンプレートでは名前空間上 p:tbl を使っている想定もあるためフォールバック
            tr_list = tbl_el.findall(".//a:tr", namespaces=ns.mapping)
        if not tr_list:
            print("⚠️ テンプレート表に行 (a:tr) が見つかりませんでした。")
            return

        header_tr = tr_list[0]

        # 内部ヘルパ: 表セルにテキストを書き込む（PowerPoint が期待する構造を保つ）
        def _set_tbl_cell_text(cell_node: etree.ElementBase, text_value: str) -> None:
            tx_body = cell_node.find("./a:txBody", namespaces=ns.mapping)
            if tx_body is None:
                tx_body = etree.Element(f"{{{ns.mapping['a']}}}txBody")
                cell_node.insert(0, tx_body)
            body_pr = tx_body.find("./a:bodyPr", namespaces=ns.mapping)
            if body_pr is None:
                body_pr = etree.Element(f"{{{ns.mapping['a']}}}bodyPr")
                tx_body.insert(0, body_pr)
            lst_style = tx_body.find("./a:lstStyle", namespaces=ns.mapping)
            if lst_style is None:
                lst_style = etree.Element(f"{{{ns.mapping['a']}}}lstStyle")
                insert_idx = 1 if len(tx_body) >= 1 else 0
                tx_body.insert(insert_idx, lst_style)
            for p in list(tx_body.findall("./a:p", namespaces=ns.mapping)):
                tx_body.remove(p)
            p_el = etree.Element(f"{{{ns.mapping['a']}}}p")
            r_el = etree.Element(f"{{{ns.mapping['a']}}}r")
            t_el = etree.Element(f"{{{ns.mapping['a']}}}t")
            t_el.text = text_value
            r_el.append(t_el)
            p_el.append(r_el)
            tx_body.append(p_el)

        # 先頭行（ヘッダ）を Markdown の先頭レコードで上書き
        header_cells = header_tr.findall("./a:tc", namespaces=ns.mapping)
        if table.records:
            header_values = list(table.records[0].cells)
            for cell_el, text in zip(header_cells, header_values):
                _set_tbl_cell_text(cell_el, text)

        # ヘッダ以外の行を削除
        for tr in tr_list[1:]:
            try:
                tbl_el.remove(tr)
            except ValueError:
                # 念のため親子関係が違う場合は親から削除を試みる
                parent = tr.getparent()
                if parent is not None:
                    parent.remove(tr)

        # Markdown のレコード（先頭はヘッダと想定）を反映
        records = list(table.records)
        if len(records) <= 1:
            # ヘッダのみ、またはデータなしの場合は何もしない（ヘッダのみ残す）
            return

        for rec in records[1:]:  # 先頭はヘッダ想定
            # ヘッダ行をコピーして新規行を作る
            new_tr = etree.fromstring(etree.tostring(header_tr))
            cells = new_tr.findall("./a:tc", namespaces=ns.mapping)
            # セルテキストを流し込み（a:txBody/a:p/a:r/a:t が無ければ生成）
            for cell_el, text in zip(cells, rec.cells):
                _set_tbl_cell_text(cell_el, text)
            tbl_el.append(new_tr)

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
