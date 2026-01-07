import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class PdfElement:
    type: str
    title: str
    content: List[str] = field(default_factory=list)
    parent: Optional["PdfElement"] = field(default=None, repr=False)
    children: List["PdfElement"] = field(default_factory=list)

    def add_content(self, text: str):
        self.content.append(text)

    def add_child(self, child: "PdfElement"):
        child.parent = self
        self.children.append(child)


class PdfParserVO(ABC):
    def __init__(self):
        self.patterns: List[tuple[str, re.Pattern]] = self._get_patterns()
        # 階層構造の定義（CHAPTER > SECTION > ARTICLE > PARAGRAPH > ITEM）
        self.hierarchy = [p[0] for p in self.patterns]

    @abstractmethod
    def _get_patterns(self) -> List[tuple[str, re.Pattern]]:
        """正規表現パターンのリストを返す [(タイプ, コンパイル済みパターン), ...]
        リストの順序は階層の深さ順（浅いものから深いもの）にすること。
        """
        pass

    def normalize(self, text: str) -> str:
        """テキストの正規化"""
        # 全角スペースを半角に、タブをスペースに置換
        text = text.replace("\u3000", " ").replace("\t", " ")
        # 連続するスペースを一つに
        text = re.sub(r" +", " ", text)
        return text.strip()

    def detect_type(self, line: str) -> Optional[tuple[str, str]]:
        """行がどのパターンにマッチするか判定する"""
        for element_type, pattern in self.patterns:
            match = pattern.match(line)
            if match:
                return element_type, match.group(0)
        return None


class DefaultPdfParserVO(PdfParserVO):
    def _get_patterns(self) -> List[tuple[str, re.Pattern]]:
        return [
            ("SUPPLEMENT", re.compile(r"^(附\s*則|別\s*表)")),
            ("CHAPTER", re.compile(r"^第[一二三四五六七八九十百\d０-９]+章")),
            ("SECTION", re.compile(r"^第[一二三四五六七八九十百\d０-９]+節")),
            ("HEADING", re.compile(r"^[（\(][^０-９\d].+[）\)]$")),
            ("ARTICLE", re.compile(r"^第[\d０-９]+条")),
            ("PARAGRAPH", re.compile(r"^[０-９\d]+(?!\.)")),
            ("ITEM", re.compile(r"^[（\(][\d０-９]+[）\)]")),
        ]


class PdfParseUseCase:
    def execute(self, parser: PdfParserVO, lines: List[str]) -> List[PdfElement]:
        root_elements: List[PdfElement] = []
        current_path: Dict[str, PdfElement] = {}

        for line in lines:
            normalized_line = parser.normalize(line)
            if not normalized_line:
                continue

            detected = parser.detect_type(normalized_line)
            if detected:
                elem_type, title = detected
                new_element = PdfElement(type=elem_type, title=normalized_line)

                # コントロールブレイク: 自分より深い階層のcurrent_pathをクリア
                idx = parser.hierarchy.index(elem_type)
                for deeper_type in parser.hierarchy[idx:]:
                    if deeper_type in current_path:
                        del current_path[deeper_type]

                # 親要素を探す
                parent = None
                for i in range(idx - 1, -1, -1):
                    parent_type = parser.hierarchy[i]
                    if parent_type in current_path:
                        parent = current_path[parent_type]
                        break

                if parent:
                    parent.add_child(new_element)
                else:
                    root_elements.append(new_element)

                current_path[elem_type] = new_element
            else:
                # どのパターンにもマッチしない場合は、現在の最深要素のコンテンツに追加
                active_element = None
                for elem_type in reversed(parser.hierarchy):
                    if elem_type in current_path:
                        active_element = current_path[elem_type]
                        break

                if active_element:
                    active_element.add_content(normalized_line)
                else:
                    # まだ構造化要素が出現していない場合
                    unknown = PdfElement(type="UNKNOWN", title="Preamble")
                    unknown.add_content(normalized_line)
                    root_elements.append(unknown)
                    current_path["UNKNOWN"] = unknown

        return root_elements
