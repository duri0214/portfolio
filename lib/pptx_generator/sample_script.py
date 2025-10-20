from pathlib import Path
import argparse
import sys

# Allow running this file directly via "python lib\\pptx_generator\\sample_script.py"
# by ensuring the project root (which contains the top-level "lib" package) is on sys.path.
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent  # .../portfolio
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.pptx_generator.service import PptxToxicService

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"

# マークダウンのサンプル（必要に応じて編集してください）
SAMPLE_MD = """
# サンプルタイトル

これは段落1です。

これは段落2です。

- 箇条書き1
- 箇条書き2

| 見出しA | 見出しB |
|---------|---------|
| セルA1  | セルB1  |
| セルA2  | セルB2  |
"""

# スライド上の図形名のマッピング
# 既存テンプレートの図形名に合わせて変更してください。
# 最低限、タイトルを配置する図形名（例: "TextBox1"）を設定します。
SHAPE_NAME_MAP = {
    "title": "Title",  # タイトル用図形名
    "paragraphs": "Paragraphs",  # 段落まとめ出力用（任意）
    "bullet_list": "BulletList",  # 箇条書き出力用（任意）
    "table": "Table",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply markdown sample to a PPTX template."
    )
    parser.add_argument(
        "--template",
        required=True,
        help="Path to the PPTX template file (e.g., path/to/template.pptx)",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "output.pptx"),
        help="Path to the output PPTX file (default: lib/pptx_generator/output/output.pptx)",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=1,
        help="Target slide number (1-based).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        service = PptxToxicService()
        parsed_md = PptxToxicService.parse_markdown(SAMPLE_MD)
        template_path = Path(args.template)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        service.apply(
            template_pptx=template_path,
            output_pptx=output_path,
            source=parsed_md,
            page=args.page,
            shape_name_map=SHAPE_NAME_MAP,
        )
        print(f"✅ MarkdownSection の反映が完了しました: {output_path}")

    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"❌ 必要なフォルダ、ファイルまたはスライドが見つかりません: {e}")
        exit(1)
    except PermissionError:
        print("⚠️ PowerPointを閉じてから再実行してください。")
        exit(1)
