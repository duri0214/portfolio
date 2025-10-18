from pathlib import Path

from lib.pptx_generator.service import PptxTextReplaceService

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
        service = PptxTextReplaceService()
        # Command スタイル: 戻り値は使用せず、置換が発生したら例外で通知
        service.replace_textbox_by_name(
            template_pptx=pptx_path,
            output_pptx=output_path,
            target_shape_name=TARGET_NAME,
            new_text=NEW_TEXT,
            page=1,
        )
        print(f"✅ 書き換え完了: {output_path}")
    except PermissionError:
        print("⚠️ PowerPointを閉じてから再実行してください。")
        exit(1)
