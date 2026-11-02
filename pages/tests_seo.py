import json
import re
import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from pages import content
from pages.management.commands.build_icon_css import BASE_CLASSES, build, used_classes
from properties.models import Category, Location, Property
from properties.services import image_service
from reviews.models import Article
from reviews.templatetags.article_tags import article_body

PUBLIC_PAGES = ["/", "/properties/", "/about/", "/services/", "/contact/", "/faq/", "/guides/transfer-fees/", "/articles/", "/reviews/", "/namecard/", "/projects/"]
SELLER_PHONE = "0899999999"


def make_property(**extra):
    defaults = {
        "title": "คอนโดจริง ใกล้รถไฟฟ้า", "description": "ห้องสวยพร้อมอยู่", "price": 15000, "property_type": Property.Type.RENT,
        "category": Category.objects.get(slug="condo"), "location": Location.objects.get_or_create(name="อโศก")[0],
        "status": Property.Status.PUBLISHED, "bedrooms": 2, "bathrooms": 1, "size_usable": 45,
        "seller_name": "ผู้ขายลับ", "seller_phone": SELLER_PHONE,
    }
    return Property.objects.create(**{**defaults, **extra})


def schemas(response):
    """คืนทุก node ใน JSON-LD ของหน้า ถ้า JSON ผิดรูปเทสต์จะล้ม"""
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', response.content.decode(), re.S)
    nodes = []
    for block in blocks:
        data = json.loads(block)
        nodes.extend(data.get("@graph", [data]))
    return nodes


def types(response):
    return {node["@type"] for node in schemas(response)}


class MetaTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_public_pages_have_one_h1_canonical_description_and_valid_schema(self):
        titles = set()
        for url in PUBLIC_PAGES:
            response = self.client.get(url)
            html = response.content.decode()
            self.assertEqual(response.status_code, 200, url)
            self.assertEqual(len(re.findall(r"<h1[\s>]", html)), 1, url)
            self.assertIn(f'<link rel="canonical" href="http://testserver{url}">', html, url)
            self.assertIn('content="index, follow', html, url)
            self.assertNotIn('content="Finding House ซื้อ ขาย เช่า ฝากขายอสังหาริมทรัพย์"', html, url)
            self.assertTrue(schemas(response), url)
            titles.add(re.search(r"<title>(.*?)</title>", html, re.S)[1])
        self.assertEqual(len(titles), len(PUBLIC_PAGES))

    def test_filtered_list_is_noindex_and_canonical_drops_filters(self):
        html = self.client.get("/properties/?category=condo&page=2").content.decode()
        self.assertIn('content="noindex, follow"', html)
        self.assertIn('<link rel="canonical" href="http://testserver/properties/?page=2">', html)

    def test_private_areas_are_noindex(self):
        self.assertContains(self.client.get("/login/"), 'content="noindex, nofollow"')

    def test_home_declares_organization_and_site_search(self):
        response = self.client.get("/")
        self.assertLessEqual({"RealEstateAgent", "WebSite"}, types(response))
        website = next(node for node in schemas(response) if node["@type"] == "WebSite")
        self.assertIn("?q={search_term_string}", website["potentialAction"]["target"]["urlTemplate"])

    def test_faq_schema_matches_visible_answers(self):
        response = self.client.get("/faq/")
        faq = next(node for node in schemas(response) if node["@type"] == "FAQPage")
        self.assertEqual(len(faq["mainEntity"]), len(content.faq_items()))
        for question in faq["mainEntity"]:
            self.assertContains(response, question["name"])
            self.assertContains(response, question["acceptedAnswer"]["text"])

    def test_fee_guide_shows_review_date_and_sources(self):
        response = self.client.get("/guides/transfer-fees/")
        self.assertContains(response, content.FEE_REVIEWED.isoformat())
        for source in content.FEE_SOURCES:
            self.assertContains(response, source["url"])
        self.assertIn("Article", types(response))


class ListingSeoTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_real_listing_schema(self):
        prop = make_property()
        response = self.client.get(prop.get_absolute_url())
        self.assertContains(response, 'content="index, follow')
        self.assertContains(response, f"ทรัพย์รหัส {prop.property_code} เป็นคอนโด")
        self.assertContains(response, "15,000 บาทต่อเดือน")
        node = next(n for n in schemas(response) if n["@type"] == "RealEstateListing")
        self.assertEqual(node["identifier"], prop.property_code)
        self.assertEqual(node["offers"]["priceSpecification"]["unitCode"], "MON")
        self.assertEqual(node["offers"]["priceCurrency"], "THB")
        self.assertEqual(node["mainEntity"]["numberOfBedrooms"], 2)
        self.assertNotIn(SELLER_PHONE, json.dumps(node))
        self.assertNotIn("ผู้ขายลับ", json.dumps(node))
        self.assertIn("BreadcrumbList", types(response))

    def test_sample_listing_is_noindex_without_offer(self):
        prop = make_property(is_sample=True)
        response = self.client.get(prop.get_absolute_url())
        self.assertContains(response, 'content="noindex, follow"')
        self.assertEqual(schemas(response), [])

    def test_script_in_listing_title_cannot_break_out_of_schema(self):
        prop = make_property(title="ห้อง</script><script>alert(1)</script>")
        response = self.client.get(prop.get_absolute_url())
        self.assertNotContains(response, "<script>alert(1)")
        self.assertTrue(schemas(response))

    def test_sitemap_lists_guides_and_real_listings_but_not_samples(self):
        real, sample = make_property(), make_property(title="ตัวอย่าง", is_sample=True)
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/guides/transfer-fees/", xml)
        self.assertIn("/faq/", xml)
        self.assertIn(real.get_absolute_url(), xml)
        self.assertNotIn(sample.get_absolute_url(), xml)

    def test_list_ajax_varies_so_caches_keep_full_and_partial_apart(self):
        response = self.client.get("/properties/", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertIn("X-Requested-With", response["Vary"])
        self.assertNotContains(response, "<html")


class LlmsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.real = make_property()
        self.sample = make_property(title="ทรัพย์ตัวอย่างห้ามอ้าง", is_sample=True)
        self.draft = make_property(title="ทรัพย์ร่างห้ามอ้าง", status=Property.Status.DRAFT)
        Article.objects.create(title="บทความเผยแพร่", excerpt="สรุป", content="เนื้อหาเต็มของบทความ", is_published=True)
        Article.objects.create(title="บทความร่าง", content="เนื้อหาลับ")

    def test_index_follows_llms_format(self):
        response = self.client.get("/llms.txt")
        text = response.content.decode()
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertTrue(text.startswith("# Finding House\n\n> "))
        self.assertIn("## ความรู้", text)
        self.assertIn("http://testserver/faq/", text)
        self.assertIn("http://testserver/llms-full.txt", text)
        self.assertIn("บทความเผยแพร่", text)
        self.assertNotIn("เนื้อหาเต็มของบทความ", text)
        self.assertNotIn("บทความร่าง", text)

    def test_full_contains_knowledge_and_only_public_listings(self):
        text = self.client.get("/llms-full.txt").content.decode()
        self.assertIn(content.FEE_SUMMARY, text)
        self.assertIn(content.faq_items()[0]["a"], text)
        self.assertIn("เนื้อหาเต็มของบทความ", text)
        self.assertIn(self.real.property_code, text)
        self.assertNotIn("เนื้อหาลับ", text)
        for hidden in ("ทรัพย์ตัวอย่างห้ามอ้าง", "ทรัพย์ร่างห้ามอ้าง", SELLER_PHONE, "ผู้ขายลับ"):
            self.assertNotIn(hidden, text)

    def test_short_names_redirect_to_standard_paths(self):
        self.assertRedirects(self.client.get("/llm.txt"), "/llms.txt", status_code=301)
        self.assertRedirects(self.client.get("/llm-full.txt"), "/llms-full.txt", status_code=301)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="fh-test-media-"))
class PerformanceTests(TestCase):
    def test_icon_css_has_every_icon_in_use_and_is_up_to_date(self):
        with open("static/css/icons.css", encoding="utf-8") as file:
            current = file.read()
        self.assertEqual(current, build(used_classes() | BASE_CLASSES), "รัน manage.py build_icon_css ใหม่")
        self.assertLess(len(current), 12_000)
        for needed in ("fa-house", "fa-comments", "fa-facebook", "fa-building", "fa-store"):
            self.assertIn(f".{needed}", current)

    def test_card_uses_small_thumbnail(self):
        prop = make_property()
        buffer = BytesIO()
        Image.new("RGB", (1600, 1200), "white").save(buffer, "JPEG")
        image = image_service.add_property_image(prop, SimpleUploadedFile("p.jpg", buffer.getvalue()))
        with Image.open(image.thumbnail.path) as thumb:
            self.assertEqual((thumb.format, thumb.width), ("WEBP", 640))
        self.assertContains(self.client.get("/properties/"), image.thumbnail.url)
        path = image.thumbnail.path
        image.delete()
        self.assertFalse(Image.os.path.exists(path))

    def test_leaflet_and_all_icons_do_not_block_first_paint(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("all.min", html)
        self.assertNotRegex(html, r'<link[^>]+leaflet[^>]+stylesheet|<script[^>]+src="[^"]*leaflet')
        self.assertNotRegex(html, r"<script src=")


class ArticleBodyTests(TestCase):
    def test_structures_headings_and_lists_and_escapes(self):
        html = article_body("นำเรื่อง <b>x</b>\n\n1. หัวข้อแรก\n- ข้อย่อย <script>\n  * ข้อย่อยสอง\n\nข้อแนะนำ:\nจบ")
        self.assertIn('<h2 class="h5 mt-4">1. หัวข้อแรก</h2>', html)
        self.assertIn("<ul><li>ข้อย่อย &lt;script&gt;</li><li>ข้อย่อยสอง</li></ul>", html)
        self.assertIn("<p>นำเรื่อง &lt;b&gt;x&lt;/b&gt;</p>", html)
        self.assertIn(">ข้อแนะนำ</h2><p>จบ</p>", html)

    def test_sample_loader_still_runs(self):
        call_command("load_sample_data", verbosity=0)
        article = Article.objects.get(title__contains="ค่าธรรมเนียม")
        self.assertIn("0.01%", article.content)
