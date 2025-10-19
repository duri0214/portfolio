from dataclasses import dataclass
from typing import Iterable, cast, Sequence
from bs4.element import Tag, PageElement
from lxml import etree


class Namespaces:
    """PPTX（DrawingML/PresentationML）で使用する XML 名前空間の詳細を隠蔽する値オブジェクト。

    提供内容:
    - mapping プロパティで、lxml の find/findall に渡すためのプレフィックス→URI マップを返します。

    メモ:
    - 必要な名前空間が増えたらここに集約して追加してください。既存コードは mapping を参照するだけで自動的に反映されます。
    """

    __ns: dict[str, str] = {
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    }

    @property
    def mapping(self) -> dict[str, str]:
        return self.__ns


@dataclass(frozen=True)
class SlideLocation:
    """PPTX アーカイブ内のスライド位置を表す値オブジェクト。

    役割:
    - スライド番号（1 始まり）から、ZIP 内のスライドXMLパス（例: ppt/slides/slide1.xml）を導出します。

    注意点:
    - page が 1 未満の場合はガードとして slide1.xml を返します（フォールバック）。
    - スライドの存在確認自体は行いません（サービス層で ZIP 内存在チェックを行います）。

    例:
        SlideLocation(3).x_path  # => "ppt/slides/slide3.xml"
    """

    page: int = 1

    @property
    def x_path(self) -> str:
        """スライド XML の ZIP 内パス（例: ppt/slides/slide1.xml）を返します。"""
        if self.page < 1:
            # Guard against invalid indices; default to 1st slide
            return "ppt/slides/slide1.xml"
        return f"ppt/slides/slide{self.page}.xml"


@dataclass(frozen=True)
class TextContent:
    """図形に適用するテキスト値を表す値オブジェクト。

    役割:
    - 与えられた図形（<p:sp>）内の最初のテキストラン（<a:t>）に文字列を適用します。

    注意点:
    - 段落や複数ランの存在には対応していません。必要であればこのクラスを拡張してください。
    - 既存テキストを保持したい場合に備え、置換前の文字列を返します。
    """

    text: str

    def apply_to_shape(
        self, shape_elem: etree.ElementBase, ns: Namespaces
    ) -> str | None:
        """図形内の最初のテキストラン（<a:t>）に text を設定します。

        パラメータ:
        - shape_elem: 図形要素（<p:sp>）。
        - ns: 名前空間マップを提供する Namespaces。

        戻り値:
        - str | None: 置換前のテキストを返します。テキストランが無い場合は None。
        """
        t_elem = shape_elem.find(".//a:t", namespaces=ns.mapping)
        if t_elem is None:
            return None
        old = t_elem.text
        t_elem.text = self.text
        return old


class ShapeNameResolver:
    """図形の cNvPr@name に基づき、段階的な堅牢マッチで対象を解決する値オブジェクト。

    - 一致順序: 完全一致（大文字小文字を区別）→ 完全一致（大文字小文字を無視）→ 部分一致（大文字小文字を無視）。
    - 診断用に利用可能な図形名一覧を提供します。
    """

    def __init__(self, elements: Iterable[etree.ElementBase], ns: Namespaces):
        self._ns = ns
        self._elements: list[etree.ElementBase] = list(elements)
        self._index: list[tuple[etree.ElementBase, str | None]] = [
            (el, self._name_of(el)) for el in self._elements
        ]

    def _name_of(self, el: etree.ElementBase) -> str | None:
        nm = el.find(".//p:cNvPr", namespaces=self._ns.mapping)
        return None if nm is None else nm.get("name")

    def resolve(self, name_or_names: str | Sequence[str]) -> list[etree.ElementBase]:
        # Normalize targets
        if isinstance(name_or_names, (list, tuple, set)):
            targets = [t for t in name_or_names if isinstance(t, str) and t]
        else:
            targets = (
                [name_or_names]
                if isinstance(name_or_names, str) and name_or_names
                else []
            )
        if not targets:
            return []

        # Tier 1: exact (case-sensitive)
        exact = [el for el, nm in self._index if nm in targets]
        if exact:
            return exact

        # Tier 2: exact (case-insensitive)
        tl = {t.lower() for t in targets}
        exact_ci = [
            el for el, nm in self._index if isinstance(nm, str) and nm.lower() in tl
        ]
        if exact_ci:
            return exact_ci

        # Tier 3: substring (case-insensitive)
        subs: list[etree.ElementBase] = []
        for el, nm in self._index:
            if not isinstance(nm, str):
                continue
            nl = nm.lower()
            for t in tl:
                if t and t in nl:
                    subs.append(el)
                    break
        return subs

    def available_names(self) -> list[str]:
        return [nm for _, nm in self._index if isinstance(nm, str)]

    # 共通適用処理: 図形名で解決 → 対象抽出 → 適用（適用があれば True）
    def apply_common(
        self,
        shape_name_value: str,
        iter_targets,
        apply_target,
        build_notfound_msg,
        empty_found_msg: str | None = None,
    ) -> bool:
        targets = self.resolve(shape_name_value)
        if targets:
            applied_any = False
            for el in targets:
                real_targets = list(iter_targets(el))
                if not real_targets:
                    continue
                for rt in real_targets:
                    apply_target(rt)
                    applied_any = True
            if not applied_any and empty_found_msg:
                print(f"⚠️ 指定図形 '{shape_name_value}' は見つかったが、{empty_found_msg}")
            return applied_any
        else:
            available_names = self.available_names()
            preview = ", ".join(available_names[:10])
            more = "" if len(available_names) <= 10 else f" 他 {len(available_names) - 10} 件"
            print(build_notfound_msg(shape_name_value, preview, more))
            return False

    # 高頻度シナリオ用のラッパー: Text 適用（サービス側のクロージャを不要化）
    def apply_text_op(
        self,
        shape_name_value: str,
        txt: "TextContent",
        ns: "Namespaces",
        op_name_key: str,
    ) -> bool:
        def _iter_sp_targets(el):
            return [el]

        def _apply_text(sp):
            txt.apply_to_shape(sp, ns)

        def _build_text_notfound(name, preview, more):
            return (
                f"⚠️ 指定された図形 '{name}'（{op_name_key}）が見つかりませんでした。候補: {preview}{more}"
            )

        return self.apply_common(
            shape_name_value,
            _iter_sp_targets,
            _apply_text,
            _build_text_notfound,
        )

    # 高頻度シナリオ用のラッパー: Table 置換（サービス側のクロージャを不要化）
    def apply_table_op(
        self,
        shape_name_value: str,
        table_vo: "Table",
        ns: "Namespaces",
    ) -> bool:
        def _iter_tbl_targets(el):
            tbl_el = el.find(".//a:tbl", namespaces=ns.mapping)
            if tbl_el is None:
                tbl_el = el.find(".//p:tbl", namespaces=ns.mapping)
            return [tbl_el] if tbl_el is not None else []

        def _apply_tbl(tbl_el):
            table_vo.replace_into(tbl_el, ns)

        def _build_tbl_notfound(name, preview, more):
            return f"⚠️ 指定された表図形 '{name}' が見つかりませんでした。候補: {preview}{more}"

        return self.apply_common(
            shape_name_value,
            _iter_tbl_targets,
            _apply_tbl,
            _build_tbl_notfound,
            "表 (a:tbl/p:tbl) が見つかりませんでした。",
        )


@dataclass(frozen=True)
class BulletStyle:
    """箇条書きのレンダリング方針を表す値オブジェクト。"""

    marker: str = "•"

    def render(self, items: list[str]) -> str:
        return "\n".join(f"{self.marker} {it}" for it in items)


# ---------------- Markdown Value Objects ----------------


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
        - separator/strip をキーワード指定しても型検査で誤検出される場合がある。
        - 本実装はランタイムでは正しく動作するため、誤検出のみを抑止する目的で
        - `# type: ignore[arg-type]` を最小範囲（この呼び出し行）に限定して付与している。
        - 目的は「VO 内にライブラリ依存と型差異を閉じ込め、外部には型安全な API だけを露出する」こと。
        """
        el = cast(PageElement, element)
        return el.get_text(separator=self.separator, strip=self.strip)  # type: ignore[arg-type]


@dataclass(frozen=True)
class BulletList:
    """箇条書き1セット（ul/ol）を表す値オブジェクト。"""

    items: list[str]


@dataclass(frozen=True)
class TableRecord:
    """表の1レコード（1行）を表す値オブジェクト。"""

    cells: list[str]


@dataclass(frozen=True)
class Table:
    """表全体を表す値オブジェクト（先頭にヘッダ行を含む）。"""

    records: list[TableRecord]

    # PPTX テンプレート内の既存表 (a:tbl / p:tbl) を、この Table 内容で置換する
    def replace_into(self, tbl_el: etree.ElementBase, ns: Namespaces) -> None:
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
        if self.records:
            header_values = list(self.records[0].cells)
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

        # データ行を反映（先頭はヘッダ想定）
        records = list(self.records)
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


@dataclass(frozen=True)
class MarkdownSection:
    """Markdown の内容を中立的な構造にした値オブジェクト。"""

    title: str | None
    paragraphs: list[str]
    bullet_list: BulletList | None
    table: Table | None
