"""คำสั่งอ่านข้อมูลทรัพย์ทั้งหมดอยู่ที่นี่ เพื่อคุมจำนวน query จุดเดียว"""
from django.db.models import Q

from properties.models import Category, Consignment, Location, Property

CARD_DEFERRED_FIELDS = ("description", "landmarks", "features")


def _published():
    return Property.objects.filter(status=Property.Status.PUBLISHED)


def _as_cards(queryset):
    """ฟิลด์ที่การ์ดทรัพย์ใช้ พร้อมความสัมพันธ์ ป้องกัน N+1 และไม่โหลดข้อความยาว"""
    return queryset.select_related("category", "location").prefetch_related("images").defer(*CARD_DEFERRED_FIELDS)


def search(data):
    """รับ cleaned_data จาก SearchForm คืนทรัพย์ที่ตรงเงื่อนไข"""
    items = _published()
    if q := data.get("q"):
        fields = ("title", "property_code", "description", "reference_code", "project_name", "province", "district", "subdistrict")
        condition = Q()
        for field in fields:
            condition |= Q(**{f"{field}__icontains": q})
        items = items.filter(condition)
    if data.get("type"):
        items = items.filter(property_type=data["type"])
    if data.get("category"):
        items = items.filter(category=data["category"])
    if data.get("location"):
        items = items.filter(location=data["location"])
    if data.get("price_min") is not None:
        items = items.filter(price__gte=data["price_min"])
    if data.get("price_max") is not None:
        items = items.filter(price__lte=data["price_max"])
    if data.get("bedrooms"):
        items = items.filter(bedrooms__gte=data["bedrooms"])
    for field in ("province", "sub_type", "zoning"):
        if data.get(field):
            items = items.filter(**{field: data[field]})
    order = {"price_asc": "price", "price_desc": "-price"}.get(data.get("sort"), "-published_at")
    return _as_cards(items).order_by(order, "-id")


def latest(limit):
    return _as_cards(_published()).order_by("-published_at", "-id")[:limit]


def detail_or_none(slug, user):
    """ทรัพย์ที่ยังไม่เผยแพร่ดูได้เฉพาะเจ้าของและเจ้าหน้าที่"""
    prop = (
        Property.objects.select_related("category", "location", "agent").prefetch_related("images")
        .filter(slug=slug).first()
    )
    if prop is None or prop.status == Property.Status.PUBLISHED or user.is_staff:
        return prop
    return prop if user.is_authenticated and prop.owner_id == user.id else None


def related(prop, limit=4):
    """ทรัพย์ในทำเลหรือหมวดเดียวกัน โดยทำเลเดียวกันขึ้นก่อน"""
    items = _as_cards(_published().filter(Q(location=prop.location) | Q(category=prop.category)).exclude(pk=prop.pk))
    return sorted(items[:40], key=lambda item: item.location_id != prop.location_id)[:limit]


def compare_items(ids):
    return _as_cards(_published().filter(pk__in=ids))


def favorites(user):
    return _as_cards(_published().filter(bookmarked_by__user=user))


def bookmarked_ids(user):
    if not user.is_authenticated:
        return set()
    return set(user.bookmarks.values_list("property_id", flat=True))


def my_listings(user):
    return _as_cards(user.listings.all())


def my_consignments(user):
    return Consignment.objects.filter(owner=user).only("property_type", "district", "province", "status", "owner_id")


def categories():
    return Category.objects.only("name", "slug", "code_prefix", "sort_order")


def locations():
    return Location.objects.only("name", "slug")


def provinces():
    """จังหวัดที่มีทรัพย์เผยแพร่อยู่จริง สำหรับตัวกรอง"""
    return _published().exclude(province="").order_by("province").values_list("province", flat=True).distinct()


def map_points(limit=300):
    """ข้อมูลหมุดบนแผนที่ เอาเฉพาะทรัพย์ที่เผยแพร่และมีพิกัด"""
    items = (
        _published().filter(latitude__isnull=False, longitude__isnull=False)
        .select_related("location", "category")
        .only(
            "title", "slug", "property_code", "reference_code", "price", "property_type", "latitude", "longitude",
            "bedrooms", "bathrooms", "size_usable", "size_land", "location__name", "category__slug",
        )[:limit]
    )
    return [_map_point(p) for p in items]


def _map_point(p):
    area = f"{p.size_usable:,.0f} ตร.ม." if p.size_usable else (f"{p.size_land:,.0f} ตร.ว." if p.size_land else "")
    specs = [f"{p.bedrooms} ห้องนอน" if p.bedrooms else "", f"{p.bathrooms} ห้องน้ำ" if p.bathrooms else "", area]
    return {
        "id": p.pk,
        "lat": p.latitude,
        "lng": p.longitude,
        "price": float(p.price),
        "price_text": f"{p.price:,.0f}",
        "type": p.property_type,
        "type_text": p.get_property_type_display(),
        "title": p.title,
        "code": p.display_code,
        "location": p.location.name,
        "icon": p.category.icon,
        "specs": " · ".join(s for s in specs if s),
        "url": p.get_absolute_url(),
    }
