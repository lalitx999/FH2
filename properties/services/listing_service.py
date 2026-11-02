from django.conf import settings

from properties.models import Bookmark, Property


class ListingError(Exception):
    """ข้อความใน exception นี้แสดงให้ผู้ใช้เห็นได้"""


def create_listing(form, user):
    """ประกาศจากผู้ใช้เริ่มเป็นร่างเสมอ ต้องผ่านเจ้าหน้าที่ก่อนเผยแพร่"""
    prop = form.save(commit=False)
    prop.owner = user
    prop.is_direct_seller = True
    prop.status = Property.Status.DRAFT
    prop.save()
    return prop


def submit_for_review(prop):
    count = prop.images.count()
    if count < settings.MIN_LISTING_IMAGES:
        raise ListingError(f"ต้องมีรูปอย่างน้อย {settings.MIN_LISTING_IMAGES} รูป (ตอนนี้มี {count} รูป)")
    prop.status = Property.Status.REVIEW
    prop.save(update_fields=["status", "updated_at"])


def set_status(prop, status):
    if status not in Property.Status.values:
        raise ListingError("สถานะไม่ถูกต้อง")
    prop.status = status
    prop.save(update_fields=["status", "published_at", "updated_at"] if prop.published_at else None)


def toggle_bookmark(user, prop):
    """คืน True เมื่อบันทึก False เมื่อเอาออก"""
    bookmark, created = Bookmark.objects.get_or_create(user=user, property=prop)
    if not created:
        bookmark.delete()
    return created
