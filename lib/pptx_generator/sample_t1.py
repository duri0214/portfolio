from zipfile import ZipFile
from lxml import etree
from pathlib import Path

# 入力/出力と置換条件
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"

pptx_path = TEMPLATES_DIR / "template.pptx"
output_path = OUTPUT_DIR / "output.pptx"
TARGET_NAME = "TextBox1"
NEW_TEXT = "Hello, world!"

if __name__ == "__main__":
    try:
        if not pptx_path.exists():
            raise FileNotFoundError(f"テンプレート PPTX が見つかりません: {pptx_path}")
        if not OUTPUT_DIR.exists():
            raise FileNotFoundError(f"出力フォルダが見つかりません: {OUTPUT_DIR}")

        # pptxを読み込み、全ファイルをメモリに保持
        with ZipFile(str(pptx_path), "r") as input_zip:
            zip_contents = {
                item.filename: input_zip.read(item.filename)
                for item in input_zip.infolist()
            }

        # スライドXMLをパース
        xml_content = zip_contents["ppt/slides/slide1.xml"]
        root = etree.fromstring(xml_content)

        # 変更前XML（pretty print）を表示
        before_xml_pretty = etree.tostring(root, pretty_print=True, encoding="unicode")
        print("===== BEFORE: ppt/slides/slide1.xml =====")
        print(before_xml_pretty)
        print("===== END BEFORE =====")

        ns_p = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        ns_a = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}

        # 対象テキストボックスを検索
        for elem in root.xpath(
            "//p:sp[p:nvSpPr/p:cNvPr[@name=$target]]",
            namespaces=ns_p,
            target=TARGET_NAME,
        ):
            txBody = elem.find(".//a:txBody", namespaces=ns_a)
            if txBody is not None:
                # 既存段落をすべて削除
                for p in list(txBody.findall(".//a:p", namespaces=ns_a)):
                    txBody.remove(p)

                # 新しい段落を作り、ランとテキストを追加
                p_new = etree.SubElement(
                    txBody, "{http://schemas.openxmlformats.org/drawingml/2006/main}p"
                )
                r_new = etree.SubElement(
                    p_new, "{http://schemas.openxmlformats.org/drawingml/2006/main}r"
                )
                t_new = etree.SubElement(
                    r_new, "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
                )
                t_new.text = NEW_TEXT

        # 変更後XML（pretty print）を表示
        after_xml_pretty = etree.tostring(root, pretty_print=True, encoding="unicode")
        print("===== AFTER: ppt/slides/slide1.xml =====")
        print(after_xml_pretty)
        print("===== END AFTER =====")

        # 編集済みXMLを書き戻す
        zip_contents["ppt/slides/slide1.xml"] = etree.tostring(
            root, xml_declaration=True, encoding="utf-8"
        )

        # 新しいpptxとして書き出す
        with ZipFile(str(output_path), "w") as output_zip:
            for filename, data in zip_contents.items():
                output_zip.writestr(filename, data)

        print(f"✅ 書き換え完了: {output_path}")

    except PermissionError:
        print("⚠️ PowerPointを閉じてから再実行してください。")
        exit(1)
