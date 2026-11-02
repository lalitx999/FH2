import uuid
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont, ImageOps

from properties.models import ConsignmentDeed, ConsignmentImage, PropertyImage

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_SIDE = 1920
THUMBNAIL_WIDTH = 640
WATERMARK = "Finding House"


class UploadError(Exception):
    """ข้อความใน exception นี้แสดงให้ผู้ใช้เห็นได้"""


def _check_size(file):
    if file.size > settings.MAX_UPLOAD_BYTES:
        limit = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise UploadError(f"ไฟล์ {file.name} ใหญ่เกิน {limit} MB")


def _open_image(file):
    """ตรวจจากเนื้อไฟล์จริง ไม่เชื่อนามสกุล"""
    _check_size(file)
    try:
        image = Image.open(file)
        image.load()
    except Exception:
        raise UploadError(f"ไฟล์ {file.name} ไม่ใช่รูปภาพที่รองรับ")
    if image.format not in ALLOWED_IMAGE_FORMATS:
        raise UploadError(f"ไฟล์ {file.name} ไม่รองรับ ใช้ได้เฉพาะ JPG, PNG, WEBP")
    return ImageOps.exif_transpose(image).convert("RGB")


def _to_jpeg(image, watermark=False):
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
    if watermark:
        font = ImageFont.load_default(size=max(16, int(image.height * 0.035)))
        draw = ImageDraw.Draw(image)
        left, top, right, bottom = draw.textbbox((0, 0), WATERMARK, font=font)
        margin = int(image.width * 0.03)
        x = image.width - (right - left) - margin
        y = image.height - (bottom - top) - margin
        draw.text((x, y), WATERMARK, font=font, fill="white", stroke_width=2, stroke_fill="#245C49", anchor="lt")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    return ContentFile(buffer.getvalue(), name=f"{uuid.uuid4().hex}.jpg")


def _to_thumbnail(image):
    """การ์ดแสดงกว้างไม่เกิน 640px ไม่ต้องโหลดรูป 1920px ทั้งหน้า"""
    thumb = image.copy()
    thumb.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_WIDTH), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    thumb.save(buffer, format="WEBP", quality=76, method=4)
    return ContentFile(buffer.getvalue(), name=f"{uuid.uuid4().hex}.webp")


def add_property_image(prop, file):
    count = prop.images.count()
    if count >= settings.MAX_LISTING_IMAGES:
        raise UploadError(f"อัปโหลดได้สูงสุด {settings.MAX_LISTING_IMAGES} รูป")
    image = _open_image(file)
    content = _to_jpeg(image, watermark=True)
    return PropertyImage.objects.create(
        property=prop, image=content, thumbnail=_to_thumbnail(image), is_cover=count == 0, order=count + 1,
    )


def delete_property_image(image):
    prop, was_cover = image.property, image.is_cover
    image.delete()
    if was_cover:
        first = prop.images.first()
        if first:
            first.is_cover = True
            first.save(update_fields=["is_cover"])


def set_cover_image(image):
    with transaction.atomic():
        image.property.images.update(is_cover=False)
        image.is_cover = True
        image.save(update_fields=["is_cover"])


def add_consignment_image(consignment, file):
    if consignment.images.count() >= settings.MAX_LISTING_IMAGES:
        raise UploadError(f"อัปโหลดได้สูงสุด {settings.MAX_LISTING_IMAGES} รูป")
    return ConsignmentImage.objects.create(consignment=consignment, image=_to_jpeg(_open_image(file)))


def add_consignment_deed(consignment, file):
    if consignment.deeds.count() >= settings.MAX_DEED_FILES:
        raise UploadError(f"แนบเอกสารได้สูงสุด {settings.MAX_DEED_FILES} ไฟล์")
    _check_size(file)
    is_pdf = file.read(5) == b"%PDF-"
    file.seek(0)
    content = ContentFile(file.read(), name=f"{uuid.uuid4().hex}.pdf") if is_pdf else _to_jpeg(_open_image(file))
    return ConsignmentDeed.objects.create(consignment=consignment, file=content, original_name=file.name[:255])
