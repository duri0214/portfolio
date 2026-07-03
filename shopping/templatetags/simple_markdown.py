from django import template
from django.utils.html import conditional_escape, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="simple_markdown")
def simple_markdown(value: str) -> str:
    """
    LLM分析の短文を画面表示用の最小Markdownとして整形する。

    箇条書きだけをHTML化し、それ以外の行は段落としてエスケープする。
    """
    if not value:
        return ""

    list_items = []
    paragraphs = []
    for raw_line in str(value).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ")):
            list_items.append((conditional_escape(line[2:].strip()),))
        else:
            paragraphs.append((conditional_escape(line),))

    parts = []
    if paragraphs:
        parts.append(format_html_join("", '<p class="mb-1">{}</p>', paragraphs))
    if list_items:
        list_body = format_html_join("", "<li>{}</li>", list_items)
        parts.append(mark_safe(f'<ul class="mb-0 ps-3">{list_body}</ul>'))
    return mark_safe("".join(str(part) for part in parts))
