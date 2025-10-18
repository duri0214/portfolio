from dataclasses import dataclass
from lxml import etree


class Namespaces:
    """PPTX（DrawingML/PresentationML）で使用する XML 名前空間の詳細を隠蔽する値オブジェクト。

    提供内容:
    - mapping プロパティで、lxml の find/findall に渡すためのプレフィックス→URI マップを返します。

    メモ（3ヶ月後の自分へ）:
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
    - index が 1 未満の場合はガードとして slide1.xml を返します（フォールバック）。
    - スライドの存在確認自体は行いません（サービス層で ZIP 内存在チェックを行います）。

    例:
        SlideLocation(3).zip_key()  # => "ppt/slides/slide3.xml"
    """

    index: int = 1

    def zip_key(self) -> str:
        if self.index < 1:
            # Guard against invalid indices; default to 1st slide
            return "ppt/slides/slide1.xml"
        return f"ppt/slides/slide{self.index}.xml"


@dataclass(frozen=True)
class ShapeName:
    """PowerPoint の図形論理名（cNvPr@name）を表す値オブジェクト。

    役割:
    - <p:sp>（図形）要素に対し、cNvPr@name が一致するかどうかをカプセル化して判定します。

    設計メモ:
    - 呼び出し側は XML の詳細（cNvPr 要素の場所など）を知らなくてよいようにします。
    """

    value: str

    def matches(self, shape_elem: etree._Element, ns: Namespaces) -> bool:
        """与えられた <p:sp> 要素の cNvPr@name がこのオブジェクトの値と一致する場合に True を返します。

        パラメータ:
        - shape_elem: 図形要素（<p:sp>）。
        - ns: 名前空間マップを提供する Namespaces。

        戻り値:
        - bool: 一致すれば True、そうでなければ False。
        """
        name_elem = shape_elem.find(".//p:cNvPr", namespaces=ns.mapping)
        return name_elem is not None and name_elem.get("name") == self.value


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
