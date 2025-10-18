from zipfile import ZipFile
from lxml import etree


pptx_path = "template.pptx"

if __name__ == "__main__":
    try:
        with ZipFile(pptx_path, "r") as zip_ref:
            xml_content = zip_ref.read("ppt/slides/slide1.xml")

        root = etree.fromstring(xml_content)

        # テキストボックス名を抽出
        for elem in root.xpath(
            "//p:cNvPr",
            namespaces={
                "p": "http://schemas.openxmlformats.org/presentationml/2006/main"
            },
        ):
            print(f"{elem.attrib.get("id")=}, {elem.attrib.get("name")=}")

    except PermissionError:
        print(
            "⚠️ ファイルが開いているため読み取れません。PowerPointを閉じてから再実行してください。"
        )
        exit(1)
