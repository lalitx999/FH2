import shutil
from datetime import timedelta
import tempfile
from io import BytesIO

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import EmailOTP, User
from properties.selectors.property_selector import map_points
from properties.services import image_service as services
from properties.services.consignment_service import convert_to_property
from properties.constants import FEATURES
from dashboard.forms import PropertyForm
from properties.forms import LandmarksField, ListingForm
from properties.services import loan_service
from properties.models import Bookmark, Category, Consignment, ConsignmentDeed, Location, Property, coords_from_maps_link, land_text, split_sqw, thai_slugify, total_sqw

MEDIA = tempfile.mkdtemp()
PRIVATE = tempfile.mkdtemp()


def image_file(name="a.png", size=(800, 600)):
    buffer = BytesIO()
    Image.new("RGB", size, "green").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA, PRIVATE_MEDIA_ROOT=PRIVATE, MIN_LISTING_IMAGES=2, MAX_LISTING_IMAGES=3)
class Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)
        shutil.rmtree(PRIVATE, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.category = Category.objects.get(slug="house")
        self.location = Location.objects.first()
        self.customer = User.objects.create_user("c@example.com", "pw-Long-12345")
        self.other = User.objects.create_user("o@example.com", "pw-Long-12345")
        self.agent = User.objects.create_user("a@example.com", "pw-Long-12345", role=User.Role.AGENT)

    def make_property(self, title="บ้านเดี่ยวสวยงาม", **extra):
        defaults = dict(description="d", price=1000000, category=self.category, location=self.location, status=Property.Status.PUBLISHED)
        return Property.objects.create(title=title, **{**defaults, **extra})

    def make_consignment(self, **extra):
        defaults = dict(
            owner=self.customer, owner_name="คุณเอ", owner_phone="0812345678", property_type="HOUSE",
            target_price=1000000, province="ชลบุรี", district="บางละมุง", subdistrict="หนองปรือ",
            google_maps_link="https://maps.example.com/x",
        )
        return Consignment.objects.create(**{**defaults, **extra})


class SlugAndCodeTests(Base):
    def test_thai_marks_are_kept(self):
        self.assertEqual(thai_slugify("บ้านเดี่ยว ใกล้รถไฟฟ้า"), "บ้านเดี่ยว-ใกล้รถไฟฟ้า")

    def test_duplicate_title_gets_unique_slug_and_url_works(self):
        first, second = self.make_property(), self.make_property()
        self.assertNotEqual(first.slug, second.slug)
        self.assertEqual(self.client.get(second.get_absolute_url()).status_code, 200)

    def test_code_runs_per_prefix(self):
        self.assertEqual(self.make_property().property_code, "H0001")
        self.assertEqual(self.make_property().property_code, "H0002")

    def test_reserved_slug_does_not_shadow_compare(self):
        self.assertEqual(self.make_property(title="compare").slug, "compare-2")


class PublicPageTests(Base):
    def test_public_urls_render(self):
        prop = self.make_property()
        for url in ["/", "/properties/", "/properties/compare/", prop.get_absolute_url(), "/articles/", "/reviews/",
                    "/about/", "/services/", "/projects/", "/contact/", "/login/", "/register/", "/password-reset/",
                    "/robots.txt", "/sitemap.xml", "/namecard/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_seo_tags_are_in_server_html(self):
        response = self.client.get(self.make_property().get_absolute_url())
        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, "บ้านเดี่ยวสวยงาม")

    def test_ajax_returns_partial_of_same_results(self):
        self.make_property()
        full = self.client.get("/properties/")
        partial = self.client.get("/properties/", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertContains(full, "<html")
        self.assertNotContains(partial, "<html")
        self.assertEqual(full.context["page"].paginator.count, partial.context["page"].paginator.count)
        self.assertContains(partial, "บ้านเดี่ยวสวยงาม")

    def test_bad_filter_values_do_not_crash(self):
        response = self.client.get("/properties/?price_min=abc&bedrooms=x&category=nope&page=zzz")
        self.assertEqual(response.status_code, 200)

    def test_filter_by_price(self):
        self.make_property(price=500)
        self.make_property(title="แพงมาก", price=9000000)
        response = self.client.get("/properties/?price_max=1000")
        self.assertEqual(response.context["page"].paginator.count, 1)

    def test_unpublished_hidden_except_owner_and_staff(self):
        prop = self.make_property(status=Property.Status.REVIEW, owner=self.customer)
        url = prop.get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_inquiry_ajax_valid_and_invalid(self):
        prop = self.make_property()
        data = {"property": prop.pk, "name": "ก", "email": "x@example.com", "phone": "081", "message": "สนใจ"}
        self.assertEqual(self.client.post("/inquiries/submit/", {**data, "email": "bad"}).status_code, 422)
        self.assertEqual(self.client.post("/inquiries/submit/", {**data, "website": "spam"}).status_code, 422)
        self.assertEqual(self.client.post("/inquiries/submit/", data).status_code, 200)
        self.assertEqual(prop.inquiries.count(), 1)

    def test_customer_review_waits_for_approval(self):
        data = {"reviewer_name": "ก", "rating": 5, "comment": "ดีมาก"}
        self.assertEqual(self.client.post("/reviews/submit/", data).status_code, 200)
        self.assertNotContains(self.client.get("/reviews/"), "ดีมาก")


class ListingPageTests(Base):
    def test_filter_panel_opens_only_when_filters_used(self):
        self.assertFalse(self.client.get("/properties/").context["has_filters"])
        self.assertFalse(self.client.get("/properties/?q=บ้าน&type=SALE").context["has_filters"])
        self.assertTrue(self.client.get(f"/properties/?category={self.category.slug}").context["has_filters"])
        self.assertTrue(self.client.get("/properties/?price_min=0").context["has_filters"])

    def test_pagination_keeps_filters(self):
        for n in range(13):
            self.make_property(title=f"บ้าน {n}")
        response = self.client.get("/properties/?type=SALE")
        self.assertContains(response, "type=SALE&amp;page=2")

    def test_related_prefers_same_location_and_excludes_self_and_unpublished(self):
        other_location = Location.objects.exclude(pk=self.location.pk).first()
        other_category = Category.objects.exclude(pk=self.category.pk).first()
        prop = self.make_property()
        same_category = self.make_property(title="หมวดเดียวกัน", location=other_location)
        same_location = self.make_property(title="ทำเลเดียวกัน", category=other_category)
        self.make_property(title="ไม่เกี่ยว", category=other_category, location=other_location)
        self.make_property(title="ยังไม่เผยแพร่", status=Property.Status.DRAFT)
        related = self.client.get(prop.get_absolute_url()).context["related"]
        self.assertEqual(related, [same_location, same_category])

    def test_posted_ago_is_thai(self):
        prop = self.make_property()
        self.assertEqual(prop.posted_ago, "ล่าสุด")
        prop.published_at = timezone.now() - timedelta(days=3, hours=1)
        self.assertEqual(prop.posted_ago, "3 วัน")
        prop.published_at = timezone.now() - timedelta(minutes=5)
        self.assertEqual(prop.posted_ago, "5 นาที")
        self.assertEqual(self.make_property(status=Property.Status.DRAFT).posted_ago, "")

    def test_inquiry_form_is_prefilled_with_property_code(self):
        prop = self.make_property()
        self.assertContains(self.client.get(prop.get_absolute_url()), f"สนใจทรัพย์รหัส {prop.property_code}")


class BookmarkTests(Base):
    def test_guest_gets_401_with_login_url(self):
        response = self.client.post(reverse("properties:bookmark", args=[self.make_property().pk]))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["X-Login-URL"], "/login/")

    def test_toggle(self):
        prop = self.make_property()
        self.client.force_login(self.customer)
        url = reverse("properties:bookmark", args=[prop.pk])
        self.client.post(url)
        self.assertTrue(Bookmark.objects.filter(user=self.customer, property=prop).exists())
        self.assertContains(self.client.get("/favorites/"), prop.title)
        self.client.post(url)
        self.assertFalse(Bookmark.objects.exists())


class SellFlowTests(Base):
    def form_data(self):
        return {
            "title": "บ้านลงเอง", "property_type": "SALE", "category": self.category.pk, "location": self.location.pk,
            "price": "1500000", "description": "รายละเอียด", "seller_name": "คุณเอ", "seller_phone": "081",
        }

    def test_requires_login(self):
        self.assertEqual(self.client.post("/sell/", self.form_data()).status_code, 302)
        self.assertFalse(Property.objects.exists())

    def test_user_cannot_publish_through_form(self):
        self.client.force_login(self.customer)
        self.client.post("/sell/", {**self.form_data(), "status": "PUBLISHED"})
        prop = Property.objects.get()
        self.assertEqual(prop.status, Property.Status.DRAFT)
        self.assertEqual(prop.owner, self.customer)

    def test_submit_needs_minimum_images_then_goes_to_review_not_published(self):
        self.client.force_login(self.customer)
        self.client.post("/sell/", self.form_data())
        prop = Property.objects.get()
        upload = reverse("properties:sell_image_upload", args=[prop.property_code])
        submit = reverse("properties:sell_submit", args=[prop.property_code])

        self.assertEqual(self.client.post(upload, {"file": image_file()}).status_code, 200)
        self.client.post(submit)
        prop.refresh_from_db()
        self.assertEqual(prop.status, Property.Status.DRAFT)

        self.client.post(upload, {"file": image_file()})
        self.client.post(submit)
        prop.refresh_from_db()
        self.assertEqual(prop.status, Property.Status.REVIEW)
        self.assertEqual(self.client.get("/properties/").context["page"].paginator.count, 0)

    def test_first_image_is_cover_and_max_enforced(self):
        prop = self.make_property(owner=self.customer, status=Property.Status.DRAFT)
        self.client.force_login(self.customer)
        upload = reverse("properties:sell_image_upload", args=[prop.property_code])
        for _ in range(3):
            self.assertEqual(self.client.post(upload, {"file": image_file()}).status_code, 200)
        self.assertEqual(self.client.post(upload, {"file": image_file()}).status_code, 400)
        self.assertEqual(prop.images.filter(is_cover=True).count(), 1)

    def test_non_image_rejected_even_with_image_name(self):
        prop = self.make_property(owner=self.customer, status=Property.Status.DRAFT)
        self.client.force_login(self.customer)
        fake = SimpleUploadedFile("photo.jpg", b"<script>alert(1)</script>", content_type="image/jpeg")
        response = self.client.post(reverse("properties:sell_image_upload", args=[prop.property_code]), {"file": fake})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(prop.images.count(), 0)

    def test_other_user_cannot_touch_listing(self):
        prop = self.make_property(owner=self.customer, status=Property.Status.DRAFT)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("properties:sell_images", args=[prop.property_code])).status_code, 404)
        self.assertEqual(self.client.post(reverse("properties:sell_image_upload", args=[prop.property_code]), {"file": image_file()}).status_code, 404)


class ConsignmentTests(Base):
    def test_pdf_is_allowed_as_deed_but_not_as_photo(self):
        consignment = self.make_consignment()
        self.client.force_login(self.customer)
        pdf = lambda: SimpleUploadedFile("deed.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        photo_url = reverse("properties:consignment_upload", args=[consignment.pk, "image"])
        deed_url = reverse("properties:consignment_upload", args=[consignment.pk, "deed"])
        self.assertEqual(self.client.post(photo_url, {"file": pdf()}).status_code, 400)
        self.assertEqual(self.client.post(deed_url, {"file": pdf()}).status_code, 200)

    def test_deed_is_private(self):
        consignment = self.make_consignment()
        file = SimpleUploadedFile("deed.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        deed = services.add_consignment_deed(consignment, file)
        self.assertTrue(deed.file.path.startswith(PRIVATE))
        with self.assertRaises(ValueError):
            deed.file.url
        url = reverse("dashboard:deed_file", args=[deed.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.agent)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 x")

    def test_convert_makes_draft_with_images(self):
        consignment = self.make_consignment()
        services.add_consignment_image(consignment, image_file())
        self.client.force_login(self.agent)
        self.client.post(reverse("dashboard:consignment_convert", args=[consignment.pk]))
        consignment.refresh_from_db()
        prop = consignment.converted_property
        self.assertEqual(prop.status, Property.Status.DRAFT)
        self.assertEqual(prop.images.count(), 1)
        self.assertEqual(consignment.status, Consignment.Status.APPROVED)
        # แปลงซ้ำต้องไม่เกิดประกาศที่สอง
        self.client.post(reverse("dashboard:consignment_convert", args=[consignment.pk]))
        self.assertEqual(Property.objects.count(), 1)

    def test_convert_rolls_back_on_failure(self):
        consignment = self.make_consignment()
        for _ in range(4):
            services_image = services.add_consignment_image
            with override_settings(MAX_LISTING_IMAGES=10):
                services_image(consignment, image_file())
        # รูปเกินเพดานของประกาศ ทำให้แปลงไม่สำเร็จกลางทาง
        with self.assertRaises(services.UploadError):
            convert_to_property(consignment.pk, self.agent)
        self.assertFalse(Property.objects.exists())
        consignment.refresh_from_db()
        self.assertIsNone(consignment.converted_property)


class MapAndDataTests(Base):
    def test_coords_parsed_from_common_link_formats(self):
        self.assertEqual(coords_from_maps_link("https://maps.google.com/?q=13.7324,100.5812"), (13.7324, 100.5812))
        self.assertEqual(coords_from_maps_link("https://www.google.com/maps/place/x/@13.75,100.5,15z"), (13.75, 100.5))
        self.assertEqual(coords_from_maps_link("https://maps.google.com/?q=13.7%2C100.5"), (13.7, 100.5))
        self.assertIsNone(coords_from_maps_link("https://maps.google.com/?q=ทองหล่อ"))
        self.assertIsNone(coords_from_maps_link("https://maps.google.com/?q=999,100"))

    def test_saving_fills_coordinates_but_keeps_manual_ones(self):
        link = "https://maps.google.com/?q=13.73,100.58"
        self.assertEqual(self.make_property(google_maps_link=link).latitude, 13.73)
        self.assertEqual(self.make_property(google_maps_link=link, latitude=1.5, longitude=2.5).latitude, 1.5)

    def test_map_points_only_published_with_coordinates(self):
        link = "https://maps.google.com/?q=13.73,100.58"
        shown = self.make_property(google_maps_link=link)
        self.make_property(title="ไม่มีพิกัด")
        self.make_property(title="ยังไม่เผยแพร่", google_maps_link=link, status=Property.Status.DRAFT)
        self.assertEqual([p["id"] for p in map_points()], [shown.pk])

    def test_home_always_has_map_and_only_lists_points_with_coordinates(self):
        self.assertEqual(self.client.get("/").context["map_points"], [])
        self.assertContains(self.client.get("/"), "home-map")
        self.make_property(google_maps_link="https://maps.google.com/?q=13.73,100.58")
        self.assertEqual(len(self.client.get("/").context["map_points"]), 1)

    def test_pages_send_referer_policy_required_by_map_tiles(self):
        self.assertEqual(self.client.get("/")["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_home_shows_four_featured_properties_in_old_site_order(self):
        for n in range(6):
            self.make_property(title=f"ทรัพย์ที่ {n}")
        response = self.client.get("/")
        self.assertEqual(len(response.context["latest"]), 4)
        html = response.content.decode()
        positions = [html.index(t) for t in ["ทรัพย์เด่นวันนี้", "ค้นหาทรัพย์บนแผนที่", "ฝากขายทรัพย์<br>", "fh-service-grid", "บทความ &amp; ความรู้เรื่องบ้าน"]]
        self.assertEqual(positions, sorted(positions))

    def test_map_data_escapes_html_in_title(self):
        self.make_property(title="</script><script>alert(1)</script>", google_maps_link="https://maps.google.com/?q=13.73,100.58")
        self.assertNotContains(self.client.get("/"), "<script>alert(1)")

    def test_detail_shows_map_features_landmarks_and_safe_json_ld(self):
        prop = self.make_property(
            title="</script>บ้าน", google_maps_link="https://maps.google.com/?q=13.73,100.58",
            features=["pool", "unknown_key"], landmarks=[{"name": "BTS ทองหล่อ", "distance": "450 เมตร"}],
        )
        response = self.client.get(prop.get_absolute_url())
        for text in ["detail-map", 'data-lat="13.73"', "สระว่ายน้ำ", "Unknown key", "BTS ทองหล่อ", "450 เมตร", "application/ld+json"]:
            self.assertContains(response, text)
        self.assertContains(response, "\\u003c/script>บ้าน")

    def test_landmarks_field_round_trip(self):
        field = LandmarksField()
        parsed = field.clean("BTS ทองหล่อ | 450 เมตร\n\nห้างใกล้บ้าน")
        self.assertEqual(parsed, [{"name": "BTS ทองหล่อ", "distance": "450 เมตร"}, {"name": "ห้างใกล้บ้าน", "distance": ""}])
        self.assertEqual(field.prepare_value(parsed), "BTS ทองหล่อ | 450 เมตร\nห้างใกล้บ้าน")

    def test_price_per_rai(self):
        self.assertEqual(self.make_property(price=4000000, size_land=400).price_per_rai, 4000000)

    def test_sell_form_saves_features_and_landmarks(self):
        self.client.force_login(self.customer)
        self.client.post("/sell/", {
            "title": "บ้านลงเอง", "property_type": "SALE", "category": self.category.pk, "location": self.location.pk,
            "price": "100", "description": "x", "seller_name": "ก", "seller_phone": "081",
            "features": ["pool", "gym"], "landmarks": "BTS | 1 กม.",
        })
        prop = Property.objects.get()
        self.assertEqual(prop.features, ["pool", "gym"])
        self.assertEqual(prop.landmarks, [{"name": "BTS", "distance": "1 กม."}])

    def test_load_and_remove_sample_data(self):
        call_command("load_sample_data", verbosity=0, stdout=open("/dev/null", "w"))
        call_command("load_sample_data", verbosity=0, stdout=open("/dev/null", "w"))
        samples = Property.objects.filter(is_sample=True)
        self.assertEqual(samples.count(), 15)
        self.assertEqual(samples.filter(latitude__isnull=False).count(), 15)
        self.assertTrue(Property.objects.filter(property_code="C0001", features__contains=["pool"]).exists())
        self.assertContains(self.client.get("/"), "ตัวอย่าง")
        real = self.make_property(title="ทรัพย์จริง")
        self.assertNotIn(real.property_code, set(samples.values_list("property_code", flat=True)))
        call_command("load_sample_data", remove=True, stdout=open("/dev/null", "w"))
        self.assertEqual(list(Property.objects.all()), [real])

    def test_pattaya_sample_covers_every_category_and_can_be_removed(self):
        out = open("/dev/null", "w")
        call_command("load_sample_data", pattaya=True, stdout=out)
        call_command("load_sample_data", pattaya=True, stdout=out)
        samples = Property.objects.filter(is_sample=True)
        self.assertEqual(samples.count(), 28)
        combos = set(samples.values_list("category__slug", "property_type"))
        self.assertEqual(combos, {(c.slug, t) for c in Category.objects.all() for t in Property.Type.values})
        self.assertEqual(set(samples.values_list("sale_condition", flat=True)), set(Property.SaleCondition.values))
        for prop in samples:
            self.assertLessEqual(set(prop.features), set(FEATURES), prop.property_code)
            self.assertTrue(12.7 < prop.latitude < 13.15 and 100.85 < prop.longitude < 101.05, prop.property_code)
        detail = self.client.get(samples.first().get_absolute_url())
        self.assertContains(detail, 'content="noindex, follow"')
        self.assertEqual(self.client.get("/properties/?location=jomtien").status_code, 200)
        call_command("load_sample_data", remove=True, stdout=out)
        self.assertFalse(Property.objects.filter(is_sample=True).exists())
        self.assertFalse(Location.objects.filter(slug="jomtien").exists())

    def test_consignment_land_size_converts_to_listing(self):
        consignment = self.make_consignment(property_type="LAND", land_rai=1, land_ngan=2, land_sqw=50)
        self.assertEqual(consignment.land_total_sqw, 650)
        prop = convert_to_property(consignment.pk, self.agent)
        self.assertEqual(prop.size_land, 650)


class DashboardPermissionTests(Base):
    PAGES = [
        "/dashboard/", "/dashboard/properties/", "/dashboard/properties/new/", "/dashboard/consignments/",
        "/dashboard/inquiries/", "/dashboard/customer-reviews/", "/dashboard/articles/", "/dashboard/articles/new/",
        "/dashboard/categories/", "/dashboard/categories/new/", "/dashboard/locations/", "/dashboard/locations/new/",
    ]

    def test_guest_redirected_and_customer_forbidden(self):
        for url in [*self.PAGES, "/dashboard/users/"]:
            with self.subTest(url=url):
                self.client.logout()
                self.assertEqual(self.client.get(url).status_code, 302)
                self.client.force_login(self.customer)
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_agent_sees_pages_but_not_users(self):
        self.client.force_login(self.agent)
        for url in self.PAGES:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get("/dashboard/users/").status_code, 403)
        self.assertEqual(self.client.get(f"/dashboard/users/{self.customer.pk}/").status_code, 403)

    def test_admin_can_promote_user(self):
        admin = User.objects.create_superuser("root@example.com", "pw-Long-12345")
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/dashboard/users/").status_code, 200)
        url = f"/dashboard/users/{self.customer.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"first_name": "ก", "last_name": "ข", "phone": "", "role": "AGENT", "is_active": "on"})
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_staff)

    def test_publish_sets_date_and_shows_publicly(self):
        prop = self.make_property(status=Property.Status.REVIEW)
        self.client.force_login(self.agent)
        self.client.post(f"/dashboard/properties/{prop.pk}/status/", {"status": "PUBLISHED"})
        prop.refresh_from_db()
        self.assertIsNotNone(prop.published_at)
        self.assertEqual(self.client.get(prop.get_absolute_url()).status_code, 200)

    def test_create_property_from_dashboard(self):
        self.client.force_login(self.agent)
        response = self.client.post("/dashboard/properties/new/", {
            "title": "ทรัพย์ใหม่", "description": "d", "price": "100", "property_type": "SALE",
            "category": self.category.pk, "location": self.location.pk, "status": "DRAFT",
            "source": "FINDING_HOUSE", "sale_condition": "SALE_ONLY",
        })
        prop = Property.objects.get()
        self.assertRedirects(response, f"/dashboard/properties/{prop.pk}/")

    def test_cannot_delete_category_in_use(self):
        self.make_property()
        self.client.force_login(self.agent)
        self.client.post(f"/dashboard/categories/{self.category.pk}/delete/")
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())


class CategoryFieldsTests(Base):
    def setUp(self):
        super().setUp()
        self.warehouse = Category.objects.get(slug="warehouse")

    def form_data(self, **extra):
        return {
            "title": "โกดังราชบุรี", "property_type": "SALE", "category": self.warehouse.pk, "location": self.location.pk,
            "price": "48000000", "description": "รายละเอียด", "seller_name": "คุณเอ", "seller_phone": "081", **extra,
        }

    def test_land_units_convert_both_ways(self):
        self.assertEqual(total_sqw(7, 2, 82), 3082)
        self.assertIsNone(total_sqw(None, None, None))
        self.assertEqual(split_sqw(3082), (7, 2, 82))
        self.assertEqual(land_text(3082), "7 ไร่ 2 งาน 82 ตร.ว.")

    def test_form_combines_land_and_keeps_warehouse_fields(self):
        form = ListingForm(self.form_data(
            land_rai="7", land_ngan="2", land_sqw="82", zoning="PINK", land_width="34", land_depth="240", road_name="แสงชูโต",
        ))
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.owner = self.customer
        prop = form.save()
        self.assertEqual(prop.size_land, 3082)
        self.assertEqual(prop.land_display, "7 ไร่ 2 งาน 82 ตร.ว.")
        self.assertEqual(prop.price_per_sqwah, 15574)
        self.assertEqual(prop.get_zoning_display(), "ผังสีชมพู")

    def test_form_rejects_land_parts_out_of_range(self):
        for extra in ({"land_ngan": "4"}, {"land_sqw": "100"}):
            with self.subTest(extra=extra):
                self.assertFalse(ListingForm(self.form_data(**extra)).is_valid())

    def test_fields_outside_category_and_type_are_cleared(self):
        form = ListingForm(self.form_data(bedrooms="3", deposit="abc", minimum_lease="1 ปี", rent_price="50000"))
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.owner = self.customer
        prop = form.save()
        self.assertIsNone(prop.bedrooms)
        self.assertIsNone(prop.deposit)
        self.assertEqual(prop.minimum_lease, "")
        self.assertEqual(prop.rent_price, 50000)

    def test_condo_has_no_land(self):
        form = ListingForm(self.form_data(category=Category.objects.get(slug="condo").pk, land_rai="1"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["size_land"])

    def test_rent_clears_sale_only_fields(self):
        form = ListingForm(self.form_data(property_type="RENT", rent_price="50000", transfer_fee="SPLIT", deposit="100000"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["rent_price"])
        self.assertEqual(form.cleaned_data["transfer_fee"], "")
        self.assertEqual(form.cleaned_data["deposit"], 100000)

    def test_public_form_hides_staff_fields(self):
        form = ListingForm()
        for name in ("reference_code", "status", "agent", "source"):
            self.assertNotIn(name, form.fields)
        self.assertIn("reference_code", PropertyForm().fields)

    def test_edit_form_shows_saved_land_and_selected_category(self):
        prop = self.make_property(category=self.warehouse, size_land=3082)
        form = PropertyForm(instance=prop)
        self.assertEqual((form.initial["land_rai"], form.initial["land_ngan"], form.initial["land_sqw"]), (7, 2, 82))
        html = str(form["category"])
        self.assertIn('data-slug="warehouse"', html)
        self.assertRegex(html, r'value="%d"[^>]*selected' % self.warehouse.pk)

    def test_sections_mark_which_fields_show_for_each_category(self):
        rows = {item["field"].name: item for section in ListingForm().sections() for item in section["fields"]}
        self.assertNotIn("condo", rows["zoning"]["show_for"].split(","))
        self.assertIn("warehouse", rows["zoning"]["show_for"].split(","))
        self.assertEqual(rows["title"]["show_for"], "")
        self.assertEqual(rows["deposit"]["show_type"], "RENT")
        self.assertEqual(rows["rent_price"]["show_type"], "SALE")

    def test_custom_category_shows_every_field(self):
        custom = Category.objects.create(name="หมวดใหม่")
        rows = {item["field"].name: item for section in ListingForm().sections() for item in section["fields"]}
        self.assertIn(custom.slug, rows["zoning"]["show_for"].split(","))
        form = ListingForm(self.form_data(category=custom.pk, bedrooms="2", zoning="RED"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["bedrooms"], 2)

    def test_every_dashboard_field_is_rendered(self):
        form = PropertyForm()
        rendered = {item["field"].name for section in form.sections() for item in section["fields"]}
        visible = {name for name, field in form.fields.items() if not field.widget.is_hidden}
        self.assertEqual(visible - rendered, set())

    def test_warehouse_can_reach_full_completeness(self):
        prop = self.make_property(
            title="โกดังพร้อมออฟฟิศ ราชบุรี", description="ก" * 30, category=self.warehouse,
            google_maps_link="https://maps.example.com/x", size_land=3082, features=["office_attached"],
        )
        for index in range(2):
            prop.images.create(image=f"x{index}.jpg", thumbnail=f"x{index}.webp", order=index)
        self.assertEqual(prop.completeness(), {"score": 100, "missing": []})

    def test_house_still_asks_for_bedrooms(self):
        self.assertIn("จำนวนห้องนอน/ห้องน้ำ", self.make_property().completeness()["missing"])

    def test_search_finds_reference_code_and_province(self):
        prop = self.make_property(reference_code="FH040", province="ราชบุรี", zoning="PINK", sub_type="WAREHOUSE")
        self.make_property(title="หลังอื่น")
        for query in ("q=FH040", "q=ราชบุรี", "province=ราชบุรี", "zoning=PINK", "sub_type=WAREHOUSE"):
            with self.subTest(query=query):
                self.assertEqual(list(self.client.get(f"/properties/?{query}").context["page"].object_list), [prop])

    def test_detail_shows_new_fields(self):
        prop = self.make_property(
            category=self.warehouse, size_land=3082, zoning="PINK", transfer_fee="SPLIT",
            province="ราชบุรี", district="บ้านโป่ง", subdistrict="หนองอ้อ", road_name="แสงชูโต",
        )
        response = self.client.get(prop.get_absolute_url())
        for text in ("7 ไร่ 2 งาน 82 ตร.ว.", "ผังสีชมพู", "คนละครึ่ง", "หนองอ้อ บ้านโป่ง ราชบุรี", "แสงชูโต"):
            self.assertContains(response, text)

    def test_conversion_copies_new_fields(self):
        consignment = self.make_consignment(
            property_type="WAREHOUSE", project_name="นิคมก", road_name="แสงชูโต", has_license=True, estate_name="นิคม",
        )
        prop = convert_to_property(consignment.pk, self.agent)
        self.assertEqual((prop.province, prop.district, prop.subdistrict), ("ชลบุรี", "บางละมุง", "หนองปรือ"))
        self.assertEqual((prop.project_name, prop.road_name, prop.estate_name), ("นิคมก", "แสงชูโต", "นิคม"))
        self.assertTrue(prop.has_license)


class ZoneMigrationTests(Base):
    def test_moves_zone_features(self):
        from importlib import import_module

        from django.apps import apps

        migration = import_module("properties.migrations.0006_property_category_details")
        prop = self.make_property(features=["red_zone", "pool"])
        migration.move_zone_features(apps, None)
        prop.refresh_from_db()
        self.assertEqual((prop.zoning, prop.features), ("RED", ["pool"]))
        migration.restore_zone_features(apps, None)
        prop.refresh_from_db()
        self.assertEqual(prop.features, ["pool", "red_zone"])


class LoanCalculatorTests(Base):
    def test_sale_home_uses_home_mode(self):
        response = self.client.get(self.make_property().get_absolute_url())
        self.assertContains(response, "คำนวณสินเชื่อเบื้องต้น")
        self.assertContains(response, 'data-income-ratio="40.0"')
        self.assertContains(response, 'value="1000000"')
        self.assertContains(response, "js/loan-calculator")

    def test_business_category_has_no_income_estimate(self):
        prop = self.make_property(category=Category.objects.get(slug="warehouse"))
        response = self.client.get(prop.get_absolute_url())
        self.assertContains(response, "ประมาณค่างวดเบื้องต้น")
        self.assertNotContains(response, "data-income-ratio")
        self.assertNotContains(response, 'data-loan="income"')

    def test_rent_listing_has_no_calculator(self):
        response = self.client.get(self.make_property(property_type="RENT").get_absolute_url())
        self.assertNotContains(response, "data-loan-calculator")

    def test_standalone_page_prefills_valid_price_only(self):
        self.assertContains(self.client.get("/tools/loan-calculator/?price=2950000"), 'value="2950000"')
        for bad in ("abc", "-1", "0", "๑๒", "99999999999"):
            with self.subTest(bad=bad):
                self.assertIsNone(loan_service.parse_price(bad))
                self.assertEqual(self.client.get("/tools/loan-calculator/", {"price": bad}).status_code, 200)

    def test_page_is_in_sitemap(self):
        self.assertContains(self.client.get("/sitemap.xml"), "/tools/loan-calculator/")
