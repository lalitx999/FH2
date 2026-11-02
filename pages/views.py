from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse

from inquiries.forms import InquiryForm
from pages import content
from pages.services import llms_service, schema_service
from properties.selectors import property_selector
from reviews.selectors import article_selector


PROPERTY_GROUPS = [
    {"slug": "house", "label": "บ้าน", "detail": "บ้านเดี่ยว / บ้านแฝด", "icon": "fa-house"},
    {"slug": "condo", "label": "คอนโด", "detail": "คอนโดมิเนียม", "icon": "fa-building"},
    {"slug": "land", "label": "ที่ดิน", "detail": "ที่ดิน / เก็งกำไร", "icon": "fa-tree"},
    {"slug": "townhome", "label": "ทาวน์โฮม", "detail": "ทาวน์โฮม / ทาวน์เฮาส์", "icon": "fa-landmark"},
    {"slug": "commercial", "label": "อาคารพาณิชย์", "detail": "ธุรกิจ / สำนักงาน", "icon": "fa-store"},
    {"slug": "warehouse", "label": "โรงงาน / โกดัง", "detail": "คลังสินค้า", "icon": "fa-warehouse"},
    {"slug": "hotel", "label": "โรงแรม / รีสอร์ท", "detail": "กิจการเพื่อการลงทุน", "icon": "fa-hotel"},
]


def home(request):
    return render(request, "pages/home.html", {
        "categories": property_selector.categories(),
        "locations": property_selector.locations(),
        "property_groups": PROPERTY_GROUPS,
        "latest": property_selector.latest(4),
        "bookmarked": property_selector.bookmarked_ids(request.user),
        "map_points": property_selector.map_points(),
        "articles": article_selector.latest_articles(3),
    })


def contact(request):
    return render(request, "pages/contact.html", {"inquiry_form": InquiryForm()})


def about(request):
    return render(request, "pages/about.html", {"about_summary": content.ABOUT_SUMMARY})


def faq(request):
    return render(request, "pages/faq.html", {
        "sections": content.FAQ_SECTIONS,
        "summary": content.ABOUT_SUMMARY,
        "reviewed": content.FAQ_REVIEWED,
        "schema": schema_service.to_script(
            schema_service.faq_page(request),
            schema_service.breadcrumbs(request, ("คำถามที่พบบ่อย", request.path)),
        ),
    })


def fee_guide(request):
    title = "คู่มือค่าโอนและภาษีเมื่อซื้อขายบ้านและคอนโด"
    return render(request, "pages/fee_guide.html", {
        "summary": content.FEE_SUMMARY,
        "reviewed": content.FEE_REVIEWED,
        "rows": content.FEE_ROWS,
        "measure": content.FEE_MEASURE,
        "example": content.FEE_EXAMPLE,
        "sources": content.FEE_SOURCES,
        "schema": schema_service.to_script(
            schema_service.guide_article(request, title, content.FEE_SUMMARY, content.FEE_REVIEWED),
            schema_service.breadcrumbs(request, (title, request.path)),
        ),
    })


def favicon(request):
    # เบราว์เซอร์และบอตบางตัวขอไฟล์นี้เสมอ แม้หน้าเว็บประกาศไอคอน svg ไว้แล้ว
    return redirect(static("favicon.svg"), permanent=True)


def _text_response(body):
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response


def llms(request):
    return _text_response(llms_service.build_index(schema_service.base_url(request)))


def llms_full(request):
    return _text_response(llms_service.build_full(schema_service.base_url(request)))


def robots(request):
    lines = [
        "User-agent: *",
        "Disallow: /dashboard/",
        "Disallow: /profile/",
        "Disallow: /my-listings/",
        "Disallow: /chat/",
        "Disallow: /sell/",
        "Disallow: /favorites/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
