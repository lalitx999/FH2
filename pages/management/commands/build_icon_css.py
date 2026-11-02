"""สร้าง static/css/icons.css จาก Font Awesome เฉพาะไอคอนที่เว็บใช้จริง

all.min.css ขนาด 90 KB บล็อกการแสดงผลทุกหน้า รันคำสั่งนี้ใหม่เมื่อใช้ไอคอนใหม่
(มีเทสต์ตรวจว่าไอคอนที่ใช้อยู่ในไฟล์ครบ)
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

SOURCE = "static/vendor/fontawesome-7.3.1/css/all.min.css"
OUTPUT = "static/css/icons.css"
SCAN = (("templates", "*.html"), ("static/js", "*.js"), (".", "*.py"))
SKIP_DIRS = {".venv", "staticfiles", "migrations", "node_modules"}
BASE_CLASSES = {"fa", "fas", "far", "fab", "fa-solid", "fa-regular", "fa-brands", "fa-classic"}
ICON_CLASS = re.compile(r"\bfa-[a-z0-9]+(?:-[a-z0-9]+)*\b")
FONT_FAMILIES = ('"Font Awesome 7 Brands"', '"Font Awesome 7 Free"')
HEADER = (
    "/* สร้างด้วย manage.py build_icon_css ห้ามแก้เอง\n"
    " * Font Awesome Free 7.3.1 - https://fontawesome.com\n"
    " * License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License)\n"
    " */\n"
)


def used_classes():
    used = set()
    for folder, pattern in SCAN:
        for path in (settings.BASE_DIR / folder).rglob(pattern):
            parts = set(path.relative_to(settings.BASE_DIR).parts)
            if not parts & SKIP_DIRS and path.name != "build_icon_css.py":
                used.update(ICON_CLASS.findall(path.read_text(encoding="utf-8")))
    return used


def _rules(css):
    """แยก rule ระดับบนสุดโดยนับวงเล็บปีกกา"""
    depth = start = 0
    for index, char in enumerate(css):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                yield css[start:index + 1]
                start = index + 1


def _keep_rule(rule, wanted):
    selector, _, body = rule.partition("{")
    if selector.startswith("@keyframes"):
        return None
    if selector.startswith("@font-face"):
        if not any(family in body for family in FONT_FAMILIES):
            return None
        rule = rule.replace("font-display:block", "font-display:swap")
        return rule.replace("../webfonts/", "../vendor/fontawesome-7.3.1/webfonts/")
    if selector.startswith("@"):
        return rule
    kept = []
    for part in selector.split(","):
        classes = {name[1:] for name in re.findall(r"\.[a-z0-9-]+", part)}
        if classes <= wanted and (classes or part.startswith(":")):
            kept.append(part)
    return f"{','.join(kept)}{{{body}" if kept else None


def build(wanted):
    css = re.sub(r"/\*.*?\*/", "", (settings.BASE_DIR / SOURCE).read_text(encoding="utf-8"), flags=re.S)
    kept = (_keep_rule(rule, wanted) for rule in _rules(css))
    return HEADER + "".join(rule for rule in kept if rule) + "\n"


class Command(BaseCommand):
    help = "สร้างไฟล์ CSS ไอคอนเฉพาะที่ใช้จริง"

    def handle(self, *args, **options):
        output = settings.BASE_DIR / OUTPUT
        output.write_text(build(used_classes() | BASE_CLASSES), encoding="utf-8")
        self.stdout.write(f"{Path(OUTPUT).name}: {output.stat().st_size / 1024:.1f} KB")
