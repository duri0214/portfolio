import sys
import os
from pypdf import PdfReader
from lib.llm.valueobject.pdf_parser import (
    PdfParseUseCase,
    DefaultPdfParserVO,
    PdfElement,
)


def print_elements(elements: list[PdfElement], indent: int = 0):
    for elem in elements:
        prefix = "  " * indent
        print(f"{prefix}[{elem.type}] {elem.title}")
        for line in elem.content:
            print(f"{prefix}  {line}")
        print_elements(elem.children, indent + 1)


def main():
    # 引数があればそれを使用、なければデフォルトのパスを使用
    if len(sys.argv) >= 2:
        pdf_path = sys.argv[1]
    else:
        # デフォルトのファイルパス
        script_dir = os.path.dirname(__file__)
        pdf_path = os.path.abspath(
            os.path.join(script_dir, "../pdf_sample/条立ての文書サンプル.pdf")
        )

    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        if len(sys.argv) < 2:
            print("Usage: python pdf_parser.py <pdf_file_path>")
        return

    try:
        reader = PdfReader(pdf_path)
        all_lines = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.splitlines())

        use_case = PdfParseUseCase()
        parser = DefaultPdfParserVO()
        elements = use_case.execute(parser, all_lines)

        print_elements(elements)

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # プロジェクトルートをsys.pathに追加
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    main()
