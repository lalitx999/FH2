import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")
EXTERNAL_ASSET = re.compile(r"""<(?:script|link|img)[^>]+(?:src|href)=["'](?:https?:)?//""", re.I)
SOURCES = [
    *Path(settings.BASE_DIR, "templates").rglob("*.*"),
    Path(settings.BASE_DIR, "static/css/app.css"),
    Path(settings.BASE_DIR, "static/js/app.js"),
]


class DesignRuleTests(SimpleTestCase):
    """กติกาออกแบบของโปรเจกต์ ถ้าเผลอใส่ test จะฟ้อง"""

    def test_no_emoji(self):
        for path in SOURCES:
            with self.subTest(path=path.name):
                self.assertIsNone(EMOJI.search(path.read_text(encoding="utf-8")))

    def test_no_cdn_assets(self):
        for path in SOURCES:
            with self.subTest(path=path.name):
                self.assertIsNone(EXTERNAL_ASSET.search(path.read_text(encoding="utf-8")))

    def test_no_gradient(self):
        for path in SOURCES:
            with self.subTest(path=path.name):
                self.assertNotIn("gradient", path.read_text(encoding="utf-8"))

    def test_buttons_are_pill_shaped(self):
        css = Path(settings.BASE_DIR, "static/css/app.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.btn \{\s*--bs-btn-border-radius: 50rem")
