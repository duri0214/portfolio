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

        ns = {
            "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        }

        # 対象テキストボックスを検索して文字更新
        for sp in root.findall(".//p:sp", namespaces=ns):
            name_elem = sp.find(".//p:cNvPr", namespaces=ns)
            if name_elem is not None and name_elem.get("name") == TARGET_NAME:
                t_elem = sp.find(".//a:t", namespaces=ns)
                if t_elem is not None:
                    print(
                        f"✅ {TARGET_NAME} を書き換え: '{t_elem.text}' → '{NEW_TEXT}'"
                    )
                    t_elem.text = NEW_TEXT

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
