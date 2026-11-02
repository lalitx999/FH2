import re

from django import template
from django.utils.html import escape, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()

NUMBERED_HEADING = re.compile(r"^\d+\.\s+")
BULLET = re.compile(r"^\s*[-*]\s+")


@register.filter
def article_body(text):
    """แปลงเนื้อหาข้อความล้วนเป็นหัวข้อและรายการ เพื่อให้คนและ AI แยกโครงเรื่องได้ ทุกส่วนถูก escape"""
    parts, bullets = [], []

    def flush():
        if bullets:
            parts.append(format_html_join("", "<li>{}</li>", ((item,) for item in bullets)).join(("<ul>", "</ul>")))
            bullets.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if BULLET.match(raw):
            bullets.append(BULLET.sub("", raw).strip())
            continue
        flush()
        if not line:
            continue
        if NUMBERED_HEADING.match(line) or (line.endswith(":") and len(line) < 60):
            parts.append(f'<h2 class="h5 mt-4">{escape(line.rstrip(":"))}</h2>')
        else:
            parts.append(f"<p>{escape(line)}</p>")
    flush()
    return mark_safe("".join(parts))
