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


@dataclass(frozen=True)
class MarkdownSection:
    """Markdown の内容を中立的な構造にした値オブジェクト。"""

    title: str | None
    paragraphs: list[str]
    bullet_list: BulletList | None
    table: Table | None
