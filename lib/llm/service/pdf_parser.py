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
    script_dir = os.path.dirname(__file__)
    pdf_path = os.path.abspath(
        os.path.join(script_dir, "../pdf_sample/条立ての文書サンプル.pdf")
    )

    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
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
    main()
