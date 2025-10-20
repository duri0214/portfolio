# lib/pptx_generator

PPTX テンプレートを XML レベルで編集し、Markdown やクエリ結果をスライドへ差し込むためのライブラリです。テンプレートの所在（templates や media 等）に依存せず、呼び出し側からファイルパスを渡すだけで動作する設計です。

## 方針（I/O 分離）
- ライブラリはテンプレートファイルを同梱しません（アプリ層やテストで任意のパスを指定してください）。
- 入力: template_pptx は絶対/相対パスどちらでも可。
- 出力: output_pptx は呼び出し側で場所を決めてください（例: 一時フォルダ、media 配下など）。

## 使い方

### 1) Django アプリから利用する場合（media を想定）
注: ここではUI（アップロード画面や図形名マッピング画面）の実装は対象外です。あくまで「アップロード等で取得したファイルパスをライブラリに渡す」最小例のみを示します。
```python
# views.py（例）
from pathlib import Path
from django.http import FileResponse
from lib.pptx_generator.service import PptxToxicService

# この dict は、ライブラリ内の論理キー（title/paragraphs/bullet_list/table）を、
# テンプレートPPTX（template.pptx）の図形名に対応づけるためのマッピングです。
# ここで指定した図形名に対してテキストや表の置換が行われます。テンプレート内の実際の図形名に合わせて編集してください。
SHAPE_NAME_MAP = {
    "title": "Title",
    "paragraphs": "Paragraphs",
    "bullet_list": "BulletList",
    "table": "Table",
}

def generate_slide(request):
    # media へ保存済みのテンプレートを利用する例
    template_path = Path(request.FILES["template"].temporary_file_path())
    markdown_text = request.POST.get("markdown", "# タイトル\n本文\n")

    section = PptxToxicService.parse_markdown(markdown_text)
    output_path = Path("/tmp/output.pptx")  # 任意の保存先

    PptxToxicService.apply(
        template_pptx=template_path,
        output_pptx=output_path,
        source=section,
        page=1,
        shape_name_map=SHAPE_NAME_MAP,
    )
    return FileResponse(open(output_path, "rb"), as_attachment=True, filename="report.pptx")
```

### 2) スクリプト／テストから利用する場合
```python
from pathlib import Path
from lib.pptx_generator.service import PptxToxicService

# この dict は、ライブラリ内の論理キー（title/paragraphs/bullet_list/table）を、
# テンプレートPPTX（template.pptx）の図形名に対応づけるためのマッピングです。
# ここで指定した図形名に対してテキストや表の置換が行われます。テンプレート内の実際の図形名に合わせて編集してください。
SHAPE_NAME_MAP = {
    "title": "Title",
    "paragraphs": "Paragraphs",
    "bullet_list": "BulletList",
    "table": "Table",
}

md_text = """
# サンプルタイトル
本文
- 箇条書き
| A | B |
|---|---|
| a | b |
"""

section = PptxToxicService.parse_markdown(md_text)
PptxToxicService.apply(
    template_pptx=Path("path/to/template.pptx"),
    output_pptx=Path("path/to/output.pptx"),
    source=section,
    page=1,
    shape_name_map=SHAPE_NAME_MAP,
)
```

### 3) サンプルスクリプトの実行方法
`lib/pptx_generator/sample_script.py` は固定のパスからテンプレートを読み込むのではなく、実行時引数で指定したファイルパスを使って処理します（「2) スクリプト／テストから利用する場合」の実行例）。

```powershell
# PowerShell 例（相対パス指定での最小実行例）
python lib\pptx_generator\sample_script.py --template lib\\pptx_generator\\sample_template.ppt
```

- --template: 入力テンプレートの PPTX ファイルパス（必須）
- --output: 出力 PPTX ファイルパス（省略時は lib/pptx_generator/output/output.pptx）
- --page: 反映対象スライド番号（1 始まり）

## 補足
- `service.PptxToxicService.apply` は図形名マッピング（shape_name_map）の指定を必須にしています。テンプレート内の図形名に合わせて設定してください。
- 表の挿入は既存表（a:tbl / p:tbl）を置換する方式です。画像（p:pic）は対象外です。
- 実行はプロジェクトルートから行うことを推奨します。PowerPoint が出力先ファイルを開いていると `PermissionError` になるため、再実行前に閉じてください。
