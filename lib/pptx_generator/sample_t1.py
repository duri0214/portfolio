from zipfile import ZipFile
from lxml import etree
from pathlib import Path

# 入力/出力と置換条件（必要に応じて変更してください）
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"

# templates フォルダは必須（存在しなければ例外で中断）
# output フォルダも必須（存在しなければ例外で中断）
if not TEMPLATES_DIR.exists():
    raise FileNotFoundError(f"templates フォルダが見つかりません: {TEMPLATES_DIR}")
if not OUTPUT_DIR.exists():
    raise FileNotFoundError(f"output フォルダが見つかりません: {OUTPUT_DIR}")

pptx_path = TEMPLATES_DIR / "template.pptx"
output_path = OUTPUT_DIR / "output.pptx"
TARGET_NAME = "TextBox1"
NEW_TEXT = "Hello, world!"

if __name__ == "__main__":
    try:
        # 前提チェック
        if not pptx_path.exists():
            raise FileNotFoundError(f"テンプレート PPTX が見つかりません: {pptx_path}")
        # まず読み込む
        with ZipFile(str(pptx_path), "r") as zin:
            # 全ファイルをメモリに保持
            zip_contents = {
                item.filename: zin.read(item.filename) for item in zin.infolist()
            }

        # XML をパース
        xml_content = zip_contents["ppt/slides/slide1.xml"]
        root = etree.fromstring(xml_content)

        ns_p = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        ns_a = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}

        # 対象テキストボックスを検索して更新
        for elem in root.xpath(
            "//p:sp[p:nvSpPr/p:cNvPr[@name=$target]]",
            namespaces=ns_p,
            target=TARGET_NAME,
        ):
            txBody = elem.find(".//a:txBody", namespaces=ns_a)
            if txBody is not None:
                # 既存の段落(a:p)を全削除
                for p in list(txBody.findall(".//a:p", namespaces=ns_a)):
                    txBody.remove(p)
                # 新しいテキストを作成
                p = etree.SubElement(
                    txBody, "{http://schemas.openxmlformats.org/drawingml/2006/main}p"
                )
                r = etree.SubElement(
                    p, "{http://schemas.openxmlformats.org/drawingml/2006/main}r"
                )
                t = etree.SubElement(
                    r, "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
                )
                t.text = NEW_TEXT

        # 編集済みXMLを書き戻す
        zip_contents["ppt/slides/slide1.xml"] = etree.tostring(
            root, xml_declaration=True, encoding="utf-8"
        )

        # 新しいpptxとして書き出す
        with ZipFile(str(output_path), "w") as zout:
            for filename, data in zip_contents.items():
                zout.writestr(filename, data)

        print(f"✅ 書き換え完了: {output_path}")

    except PermissionError:
        print("⚠️ PowerPointを閉じてから再実行してください。")
        exit(1)
