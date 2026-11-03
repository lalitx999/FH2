from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from properties.models import Category, Consignment, Location, Property

from .image_service import UploadError, add_property_image

CATEGORY_KEYWORDS = {
    "HOUSE": "บ้าน",
    "CONDO": "คอนโด",
    "LAND": "ที่ดิน",
    "WAREHOUSE": "โรงงาน",
    "HOTEL": "โรงแรม",
}


class ConsignmentError(Exception):
    """ข้อความใน exception นี้แสดงให้ผู้ใช้เห็นได้"""


def create_consignment(form, user):
    consignment = form.save(commit=False)
    consignment.owner = user
    consignment.save()
    return consignment


def submit(consignment):
    count = consignment.images.count()
    if count < settings.MIN_LISTING_IMAGES:
        raise ConsignmentError(f"ต้องมีรูปอย่างน้อย {settings.MIN_LISTING_IMAGES} รูป (ตอนนี้มี {count} รูป)")
    consignment.status = Consignment.Status.PENDING
    consignment.save(update_fields=["status"])


def set_status(consignment, status):
    if status not in Consignment.Status.values:
        raise ConsignmentError("สถานะไม่ถูกต้อง")
    consignment.status = status
    consignment.save(update_fields=["status"])


def _category_for(consignment):
    return Category.objects.filter(name__icontains=CATEGORY_KEYWORDS[consignment.property_type]).first()


def request_conversion(consignment, user):
    """ตรวจเงื่อนไขทันที แล้วส่งงานแปลงรูปให้ Celery เพราะทรัพย์หนึ่งมีรูปได้ถึง 30 รูป"""
    from properties.tasks import convert_consignment_task

    if not _category_for(consignment):
        raise ConsignmentError("ยังไม่มีหมวดหมู่ที่ตรงกับประเภททรัพย์นี้ กรุณาเพิ่มหมวดหมู่ก่อน")
    convert_consignment_task.delay(consignment.pk, user.pk)


@transaction.atomic
def convert_to_property(consignment_id, user):
    """แปลงคำขอฝากขายเป็นประกาศฉบับร่าง ถ้าพังกลางทางจะไม่เหลือข้อมูลค้าง"""
    consignment = Consignment.objects.select_for_update().get(pk=consignment_id)
    if consignment.converted_property_id:
        return consignment.converted_property

    category = _category_for(consignment)
    if not category:
        raise UploadError("ยังไม่มีหมวดหมู่ที่ตรงกับประเภททรัพย์นี้")
    location, _ = Location.objects.get_or_create(name=consignment.district)
    place = f"{consignment.subdistrict} {consignment.district} {consignment.province}"
    title = consignment.project_name or f"{consignment.get_property_type_display()} {consignment.district}"
    prop = Property.objects.create(
        title=title[:200],
        description=consignment.highlights or f"ทรัพย์ฝากขาย ทำเล {place}",
        price=consignment.target_price,
        property_type=Property.Type.SALE,
        category=category,
        location=location,
        bedrooms=consignment.bedrooms,
        bathrooms=consignment.bathrooms,
        size_land=consignment.land_total_sqw,
        size_usable=consignment.size_usable,
        floors=consignment.floors,
        parking_spaces=consignment.parking_spaces,
        province=consignment.province,
        district=consignment.district,
        subdistrict=consignment.subdistrict,
        project_name=consignment.project_name,
        floor_level=consignment.floor_level,
        land_width=consignment.land_width,
        road_name=consignment.road_name,
        road_width=consignment.road_width,
        estate_name=consignment.estate_name,
        has_license=consignment.has_license,
        room_count=consignment.room_count,
        sell_with_business=consignment.sell_with_business,
        google_maps_link=consignment.google_maps_link,
        seller_name=consignment.owner_name,
        seller_phone=consignment.owner_phone,
        seller_line_id=consignment.owner_line_id,
        status=Property.Status.DRAFT,
        owner=consignment.owner,
        agent=user,
    )
    for source in consignment.images.all():
        with source.image.open("rb") as file:
            add_property_image(prop, ContentFile(file.read(), name=source.image.name))

    consignment.status = Consignment.Status.APPROVED
    consignment.converted_property = prop
    consignment.save(update_fields=["status", "converted_property"])
    return prop
