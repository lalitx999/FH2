"""QC ก่อนขึ้นระบบ: จำนวน query ต้องไม่โตตามข้อมูล และทุกหน้าต้องไม่ error ในทุกสิทธิ์"""
import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import get_resolver, reverse
from PIL import Image

from accounts.models import User
from chatbot.models import ChatMessage, ChatSession
from inquiries.models import Inquiry
from properties.models import Category, Consignment, Location, Property
from properties.services import image_service
from reviews.models import Article, CustomerReview

PASSWORD = "TestPass-2026!"
TEST_MEDIA = tempfile.mkdtemp(prefix="fh-test-media-")


def image_file():
    buffer = BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, "JPEG")
    return SimpleUploadedFile("p.jpg", buffer.getvalue(), content_type="image/jpeg")


def make_properties(count, start=0):
    category = Category.objects.get(slug="condo")
    items = []
    for n in range(start, start + count):
        location, _ = Location.objects.get_or_create(name=f"ทำเล {n}")
        prop = Property.objects.create(
            title=f"ทรัพย์ {n}", description="รายละเอียด", price=1_000_000 + n, category=category, location=location,
            status=Property.Status.PUBLISHED, latitude=13.7, longitude=100.5,
        )
        image_service.add_property_image(prop, image_file())
        items.append(prop)
    return items


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class QueryCountTests(TestCase):
    """เทียบจำนวน query ตอนข้อมูลน้อยกับข้อมูลมาก ถ้าเพิ่มขึ้นแปลว่ามี N+1"""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@example.com", PASSWORD, role=User.Role.ADMIN)
        make_properties(2)

    def count(self, url):
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        return len(queries)

    def assert_does_not_grow(self, *urls):
        before = {url: self.count(url) for url in urls}
        make_properties(8, start=2)
        for url in urls:
            self.assertEqual(self.count(url), before[url], f"N+1 ที่ {url}")

    def test_public_pages(self):
        self.assert_does_not_grow("/", "/properties/", "/sitemap.xml")

    def test_logged_in_list_pages(self):
        self.client.force_login(self.admin)
        self.assert_does_not_grow("/", "/properties/", "/dashboard/", "/dashboard/properties/", "/dashboard/categories/", "/dashboard/locations/")

    def test_property_detail_query_budget(self):
        prop = make_properties(6, start=2)[0]
        self.assertLessEqual(self.count(prop.get_absolute_url()), 8)

    def test_chat_list_and_history(self):
        self.client.force_login(self.admin)
        self.client.post("/chat/send/", {"message": "คอนโด"})
        before_chats, before_history = self.count("/dashboard/chats/"), self.count("/chat/history/")
        make_properties(3, start=2)
        for _ in range(3):
            self.client.post("/chat/send/", {"message": "คอนโด"})
        self.assertEqual(self.count("/chat/history/"), before_history)
        self.assertEqual(self.count("/dashboard/chats/"), before_chats)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class CrawlTests(TestCase):
    """เปิดทุก URL ที่ GET ได้ในทุกสิทธิ์ ห้ามมี 5xx และต้องได้สิทธิ์ตามที่ควร"""

    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user("customer@example.com", PASSWORD)
        cls.agent = User.objects.create_user("agent@example.com", PASSWORD, role=User.Role.AGENT)
        cls.admin = User.objects.create_user("admin@example.com", PASSWORD, role=User.Role.ADMIN)
        cls.prop = make_properties(1)[0]
        cls.draft = Property.objects.create(
            title="ของลูกค้า", description="x", price=1, category=cls.prop.category, location=cls.prop.location, owner=cls.customer,
        )
        cls.consignment = Consignment.objects.create(
            owner=cls.customer, owner_name="ก", owner_phone="081", owner_email="c@example.com",
            property_type="CONDO", province="กทม", district="วัฒนา", subdistrict="คลองเตยเหนือ", target_price=1,
        )
        cls.article = Article.objects.create(title="บทความ", content="เนื้อหา", is_published=True)
        cls.review = CustomerReview.objects.create(reviewer_name="ก", comment="ดี", is_approved=True)
        cls.inquiry = Inquiry.objects.create(name="ก", email="c@example.com", phone="081", message="ถาม")
        cls.chat = ChatSession.objects.create()
        ChatMessage.objects.create(session=cls.chat, role=ChatMessage.Role.USER, content="สวัสดี")

    def urls(self):
        args = {
            "properties:detail": [self.prop.slug],
            "properties:sell_images": [self.draft.property_code],
            "properties:consignment_files": [self.consignment.pk],
            "reviews:article_detail": [self.article.slug],
            "dashboard:property_edit": [self.prop.pk],
            "dashboard:consignment_detail": [self.consignment.pk],
            "dashboard:chat_detail": [self.chat.pk],
            "dashboard:user_edit": [self.customer.pk],
            "dashboard:articles_edit": [self.article.pk],
            "dashboard:categories_edit": [self.prop.category.pk],
            "dashboard:locations_edit": [self.prop.location.pk],
        }
        names = []
        for namespace in ("pages", "accounts", "properties", "reviews", "dashboard"):
            resolver = get_resolver().namespace_dict[namespace][1]
            for name, entries in resolver.reverse_dict.lists() if hasattr(resolver.reverse_dict, "lists") else []:
                if isinstance(name, str):
                    names.append((f"{namespace}:{name}", entries[0][0][0][1]))
        urls = {}
        for name, params in names:
            if not params:
                urls[name] = reverse(name)
            elif name in args:
                urls[name] = reverse(name, args=args[name])
        return urls

    def crawl(self, client):
        results = {}
        for name, url in self.urls().items():
            if name == "accounts:logout":
                continue
            results[name] = client.get(url).status_code
            self.assertLess(results[name], 500, f"{name} {url}")
        return results

    def test_every_role_gets_no_server_error_and_correct_access(self):
        guest = self.crawl(self.client_class())
        self.assertGreater(len(guest), 30)
        for name, status in guest.items():
            if name.startswith("dashboard:"):
                self.assertEqual(status, 302, name)

        client = self.client_class()
        client.force_login(self.customer)
        for name, status in self.crawl(client).items():
            if name.startswith("dashboard:"):
                self.assertEqual(status, 403, name)

        client = self.client_class()
        client.force_login(self.agent)
        agent = self.crawl(client)
        self.assertEqual(agent["dashboard:home"], 200)
        self.assertEqual(agent["dashboard:users"], 403)

        client = self.client_class()
        client.force_login(self.admin)
        admin = self.crawl(client)
        for name, status in admin.items():
            if name.startswith("dashboard:"):
                self.assertEqual(status, 200, name)

    def test_dashboard_write_actions_reject_other_roles(self):
        for path in (
            reverse("dashboard:property_status", args=[self.prop.pk]),
            reverse("dashboard:property_delete", args=[self.prop.pk]),
            reverse("dashboard:consignment_convert", args=[self.consignment.pk]),
        ):
            self.assertEqual(self.client_class().post(path).status_code, 302)
            client = self.client_class()
            client.force_login(self.customer)
            self.assertEqual(client.post(path).status_code, 403)

    def test_csrf_is_enforced_on_chat_and_inquiry(self):
        client = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(client.post("/chat/send/", {"message": "สวัสดี"}).status_code, 403)
        self.assertEqual(client.post(reverse("inquiries:submit"), {"name": "ก"}).status_code, 403)

    def test_error_pages_render_without_server_error(self):
        self.assertEqual(self.client.get("/no-such-page/").status_code, 404)
