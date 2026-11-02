from django import template
from django.templatetags.static import static

from pages.services import schema_service

register = template.Library()

NOINDEX_NAMESPACES = {"accounts", "dashboard", "chatbot"}
NOINDEX_VIEWS = {
    "properties:compare", "properties:favorites", "properties:my_listings", "properties:sell",
    "properties:sell_images", "properties:consignment_files",
}


def _view_name(request):
    match = getattr(request, "resolver_match", None)
    return match.view_name if match else ""


def _has_filters(request):
    return any(key != "page" for key in request.GET)


@register.simple_tag(takes_context=True)
def canonical_url(context):
    """ตัวกรองทุกแบบชี้กลับหน้าเดียวกัน เก็บไว้เฉพาะเลขหน้า"""
    request = context["request"]
    url = request.build_absolute_uri(request.path)
    page = request.GET.get("page", "")
    return f"{url}?page={page}" if page.isdigit() and page != "1" else url


@register.simple_tag(takes_context=True)
def robots_content(context):
    request = context["request"]
    view = _view_name(request)
    if not view or view.split(":")[0] in NOINDEX_NAMESPACES or view in NOINDEX_VIEWS:
        return "noindex, nofollow"
    if view == "properties:list" and _has_filters(request):
        return "noindex, follow"
    prop = context.get("property")
    if view == "properties:detail" and prop and not schema_service.is_indexable(prop):
        return "noindex, follow"
    return "index, follow, max-image-preview:large"


@register.simple_tag(takes_context=True)
def absolute_static(context, path):
    return context["request"].build_absolute_uri(static(path))


@register.simple_tag(takes_context=True)
def page_schema(context, kind, name=""):
    """schema ของหน้าคงที่ที่ไม่มี view ของตัวเอง"""
    request = context["request"]
    builders = {
        "home": lambda: [schema_service.organization(request), schema_service.website(request)],
        "about": lambda: [
            schema_service.organization(request),
            schema_service.web_page(request, "AboutPage", name),
            schema_service.breadcrumbs(request, (name, request.path)),
        ],
        "contact": lambda: [
            schema_service.web_page(request, "ContactPage", name),
            schema_service.breadcrumbs(request, (name, request.path)),
        ],
        "services": lambda: [
            *schema_service.services(request),
            schema_service.breadcrumbs(request, (name, request.path)),
        ],
        "namecard": lambda: [
            schema_service.person(request),
            schema_service.breadcrumbs(request, (name, request.path)),
        ],
        "page": lambda: [schema_service.breadcrumbs(request, (name, request.path))],
    }
    return schema_service.to_script(*builders[kind]())
