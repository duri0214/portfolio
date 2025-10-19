from pathlib import Path

from lib.pptx_generator.service import PptxTextReplaceService, parse_markdown

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"

pptx_path = TEMPLATES_DIR / "template.pptx"
output_path = OUTPUT_DIR / "output.pptx"

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

if __name__ == "__main__":
    try:
        service = PptxTextReplaceService()
        section = parse_markdown(SAMPLE_MD)
        service.apply_markdown_section(
            template_pptx=pptx_path,
            output_pptx=output_path,
            section=section,
            page=1,
            shape_name_map=SHAPE_NAME_MAP,
        )
        print(f"✅ MarkdownSection の反映が完了しました: {output_path}")
    except (FileNotFoundError, KeyError) as e:
        print(f"❌ 必要なフォルダ、ファイルまたはスライドが見つかりません: {e}")
        exit(1)
    except PermissionError:
        print("⚠️ PowerPointを閉じてから再実行してください。")
        exit(1)
