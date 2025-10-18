from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from zipfile import ZipFile
from lxml import etree

from lib.pptx_generator.valueobject import (
    Namespaces,
    SlideLocation,
    ShapeName,
    TextContent,
)


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
    ) -> Optional[str]:
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
        - Optional[str]: 置換が発生した場合は最初に一致した図形の置換前テキスト。該当無しは None。

        例外:
        - FileNotFoundError: 入力/出力パス不正、または対象スライドが ZIP 内に存在しない場合。
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
            raise FileNotFoundError(f"スライドが見つかりません: {x_path}")
        root = etree.fromstring(zip_contents[x_path])

        # Find and replace
        replaced_any = False
        original_text: Optional[str] = None
        for sp in root.findall(".//p:sp", namespaces=ns.mapping):
            if shape_name.matches(sp, ns):
                old = text_content.apply_to_shape(sp, ns)
                if old is not None and not replaced_any:
                    original_text = old
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

        return original_text
