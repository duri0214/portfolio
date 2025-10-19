from dataclasses import dataclass
from typing import Iterable, cast
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

    def apply_to_shape(self, shape_elem: etree._Element, ns: Namespaces) -> str | None:
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
