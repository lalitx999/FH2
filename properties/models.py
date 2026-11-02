import os
import re

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError, models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.deconstruct import deconstructible

from .constants import FEATURES

# slug ที่ชนกับ URL อื่นใน /properties/
RESERVED_SLUGS = {"compare", "create"}


def thai_slugify(text):
    """slugify ของ Django ลบสระและวรรณยุกต์ไทยทิ้ง จึงเขียนเองให้เก็บอักษรไทยครบ"""
    text = re.sub(r"[^\w฀-๿\s-]", "", text.strip().lower())
    return re.sub(r"[-\s]+", "-", text).strip("-_")


def unique_slug(model, text, instance_pk=None, max_length=220):
    base = (thai_slugify(text) or "item")[: max_length - 8]
    slug, n = base, 2
    while slug in RESERVED_SLUGS or model.objects.exclude(pk=instance_pk).filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def coords_from_maps_link(link):
    """ดึงพิกัดจากลิงก์ Google Maps เช่น ?q=13.73,100.58 หรือ /@13.73,100.58,15z"""
    match = re.search(r"(?:[?&](?:q|query|ll)=|@)(-?\d+(?:\.\d+)?)(?:,|%2C)\s*(-?\d+(?:\.\d+)?)", link or "")
    if not match:
        return None
    lat, lng = float(match[1]), float(match[2])
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


@deconstructible
class PrivateStorage(FileSystemStorage):
    """เก็บไฟล์ลับนอก MEDIA_ROOT และไม่มี URL สาธารณะ"""

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("ไฟล์ลับไม่มี URL สาธารณะ")


class Category(models.Model):
    name = models.CharField("ชื่อหมวดหมู่", max_length=100, unique=True)
    slug = models.SlugField("URL Slug", max_length=120, unique=True, allow_unicode=True, blank=True)
    code_prefix = models.CharField("อักษรนำรหัสทรัพย์", max_length=1, default="P")

    sort_order = models.PositiveSmallIntegerField("ลำดับแสดงผล", default=0)

    ICONS = {
        "house": "fa-house-chimney", "condo": "fa-building", "land": "fa-tree", "townhome": "fa-house-laptop",
        "commercial": "fa-store", "warehouse": "fa-warehouse", "hotel": "fa-hotel",
    }

    class Meta:
        verbose_name = "หมวดหมู่"
        ordering = ["sort_order", "id"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, self.pk, 120)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def icon(self):
        return self.ICONS.get(self.slug, "fa-house-chimney")


class Location(models.Model):
    name = models.CharField("ทำเล/ย่าน", max_length=100, unique=True)
    slug = models.SlugField("URL Slug", max_length=120, unique=True, allow_unicode=True, blank=True)

    class Meta:
        verbose_name = "ทำเล"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Location, self.name, self.pk, 120)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Property(models.Model):
    class Type(models.TextChoices):
        SALE = "SALE", "ขาย"
        RENT = "RENT", "เช่า"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "ร่าง"
        REVIEW = "REVIEW", "รอตรวจสอบ"
        PUBLISHED = "PUBLISHED", "เผยแพร่"
        NEGOTIATING = "NEGOTIATING", "กำลังเจรจา"
        BOOKED = "BOOKED", "จองแล้ว"
        SOLD = "SOLD", "ขาย/เช่าแล้ว"
        PAUSED = "PAUSED", "พักประกาศ"
        REJECTED = "REJECTED", "ไม่ผ่านการตรวจสอบ"

    class Source(models.TextChoices):
        FINDING_HOUSE = "FINDING_HOUSE", "Finding House"
        CO_BROKER = "CO_BROKER", "Co-Broker ภายนอก"

    class SaleCondition(models.TextChoices):
        SALE_ONLY = "SALE_ONLY", "ขายอย่างเดียว"
        SALE_AND_RENT = "SALE_AND_RENT", "ขายและมีราคาเช่า"
        SALE_WITH_TENANT = "SALE_WITH_TENANT", "ขายพร้อมผู้เช่า"

    title = models.CharField("หัวข้อประกาศ", max_length=200)
    slug = models.SlugField("URL Slug", max_length=220, unique=True, allow_unicode=True, blank=True, editable=False)
    property_code = models.CharField("รหัสทรัพย์", max_length=20, unique=True, blank=True, editable=False)
    description = models.TextField("รายละเอียด")
    price = models.DecimalField("ราคา (บาท)", max_digits=14, decimal_places=2)
    property_type = models.CharField("ประเภทประกาศ", max_length=10, choices=Type.choices, default=Type.SALE)
    category = models.ForeignKey(Category, verbose_name="หมวดหมู่", on_delete=models.PROTECT, related_name="properties")
    location = models.ForeignKey(Location, verbose_name="ทำเล", on_delete=models.PROTECT, related_name="properties")
    status = models.CharField("สถานะ", max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    bedrooms = models.PositiveIntegerField("ห้องนอน", null=True, blank=True)
    bathrooms = models.PositiveIntegerField("ห้องน้ำ", null=True, blank=True)
    floors = models.PositiveIntegerField("จำนวนชั้น", null=True, blank=True)
    parking_spaces = models.PositiveIntegerField("ที่จอดรถ (คัน)", null=True, blank=True)
    size_land = models.DecimalField("ขนาดที่ดิน (ตร.ว.)", max_digits=10, decimal_places=2, null=True, blank=True)
    size_usable = models.DecimalField("พื้นที่ใช้สอย (ตร.ม.)", max_digits=10, decimal_places=2, null=True, blank=True)
    direction = models.CharField("ทิศหน้าทรัพย์", max_length=50, blank=True)
    furniture = models.CharField("เฟอร์นิเจอร์", max_length=100, blank=True)
    pet_friendly = models.BooleanField("รับสัตว์เลี้ยง", default=False)
    common_fee = models.DecimalField("ค่าส่วนกลาง (บาท/เดือน)", max_digits=10, decimal_places=2, null=True, blank=True)
    minimum_lease = models.CharField("สัญญาขั้นต่ำ", max_length=100, blank=True)
    deposit = models.DecimalField("เงินประกัน (บาท)", max_digits=12, decimal_places=2, null=True, blank=True)
    advance_payment = models.DecimalField("เงินล่วงหน้า (บาท)", max_digits=12, decimal_places=2, null=True, blank=True)
    move_in_date = models.CharField("พร้อมเข้าอยู่เมื่อ", max_length=100, blank=True)
    availability = models.BooleanField("ว่างพร้อมให้บริการ", default=True)
    source = models.CharField("แหล่งทรัพย์", max_length=20, choices=Source.choices, default=Source.FINDING_HOUSE)
    sale_condition = models.CharField("เงื่อนไขการขาย", max_length=20, choices=SaleCondition.choices, default=SaleCondition.SALE_ONLY)
    features = models.JSONField("คุณสมบัติ", default=list, blank=True)
    landmarks = models.JSONField("สถานที่ใกล้เคียง", default=list, blank=True)
    google_maps_link = models.URLField("ลิงก์ Google Maps", max_length=500, blank=True)
    latitude = models.FloatField("ละติจูด", null=True, blank=True, help_text="เว้นว่างได้ ระบบจะดึงจากลิงก์ Google Maps ที่มีพิกัด")
    longitude = models.FloatField("ลองจิจูด", null=True, blank=True)
    is_sample = models.BooleanField("ข้อมูลตัวอย่าง", default=False, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="ผู้ลงประกาศ", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="listings",
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="นายหน้าผู้ดูแล", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="managed_properties",
        limit_choices_to={"is_staff": True},
    )
    is_direct_seller = models.BooleanField("ผู้ขายลงเอง", default=False)
    seller_name = models.CharField("ชื่อผู้ขาย", max_length=150, blank=True)
    seller_phone = models.CharField("เบอร์ผู้ขาย", max_length=30, blank=True)
    seller_line_id = models.CharField("LINE ID ผู้ขาย", max_length=100, blank=True)

    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)
    updated_at = models.DateTimeField("แก้ไขล่าสุด", auto_now=True)
    published_at = models.DateTimeField("เผยแพร่เมื่อ", null=True, blank=True)

    class Meta:
        verbose_name = "ประกาศ"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.property_code}] {self.title}"

    def get_absolute_url(self):
        return reverse("properties:detail", args=[self.slug])

    def _next_code(self):
        prefix = self.category.code_prefix
        codes = Property.objects.filter(property_code__regex=rf"^{prefix}\d+$").values_list("property_code", flat=True)
        highest = max((int(code[len(prefix):]) for code in codes), default=0)
        return f"{prefix}{highest + 1:04d}"

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        if self.latitude is None and self.longitude is None and (coords := coords_from_maps_link(self.google_maps_link)):
            self.latitude, self.longitude = coords
        if self.pk:
            return super().save(*args, **kwargs)
        # คนบันทึกพร้อมกันอาจได้รหัสหรือ slug ชนกัน จึงลองใหม่แทนการ error 500
        given_code = self.property_code
        for attempt in range(5):
            self.slug = unique_slug(Property, self.title)
            self.property_code = given_code or self._next_code()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.pk = None
                if attempt == 4:
                    raise

    @property
    def cover(self):
        images = list(self.images.all())
        return next((img for img in images if img.is_cover), images[0] if images else None)

    @property
    def feature_list(self):
        fallback = lambda key: (key.replace("_", " ").capitalize(), "fa-circle-check")
        return [dict(zip(("label", "icon"), FEATURES.get(key) or fallback(key))) for key in self.features]

    @property
    def posted_ago(self):
        """เวลาที่ลงประกาศแบบสั้นเป็นภาษาไทย เช่น 3 วัน"""
        if not self.published_at:
            return ""
        seconds = int((timezone.now() - self.published_at).total_seconds())
        for size, unit in ((31536000, "ปี"), (2592000, "เดือน"), (86400, "วัน"), (3600, "ชม."), (60, "นาที")):
            if seconds >= size:
                return f"{seconds // size} {unit}"
        return "ล่าสุด"

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def info_rows(self):
        """ตารางข้อมูลพื้นฐานในหน้ารายละเอียด แสดงเฉพาะค่าที่มี"""
        baht = lambda value: f"{value:,.0f} บาท" if value else ""
        rows = [
            ("fa-hashtag", "รหัสทรัพย์", self.property_code),
            ("fa-tag", "ประเภทประกาศ", self.get_property_type_display()),
            ("fa-house", "หมวดหมู่", self.category.name),
            ("fa-location-dot", "ทำเล", self.location.name),
            ("fa-file-contract", "เงื่อนไข", self.get_sale_condition_display() if self.property_type == self.Type.SALE else ""),
            ("fa-mountain-sun", "ขนาดที่ดิน", f"{self.size_land:,.2f} ตร.ว." if self.size_land else ""),
            ("fa-ruler-combined", "พื้นที่ใช้สอย", f"{self.size_usable:,.2f} ตร.ม." if self.size_usable else ""),
            ("fa-bed", "ห้องนอน", self.bedrooms),
            ("fa-bath", "ห้องน้ำ", self.bathrooms),
            ("fa-layer-group", "จำนวนชั้น", self.floors),
            ("fa-car", "ที่จอดรถ", f"{self.parking_spaces} คัน" if self.parking_spaces else ""),
            ("fa-compass", "ทิศหน้าทรัพย์", self.direction),
            ("fa-couch", "เฟอร์นิเจอร์", self.furniture),
            ("fa-paw", "สัตว์เลี้ยง", "รับสัตว์เลี้ยง" if self.pet_friendly else ""),
            ("fa-coins", "ค่าส่วนกลาง", f"{self.common_fee:,.0f} บาท/เดือน" if self.common_fee else ""),
            ("fa-file-signature", "สัญญาขั้นต่ำ", self.minimum_lease),
            ("fa-piggy-bank", "เงินประกัน", baht(self.deposit)),
            ("fa-money-bill-wave", "เงินล่วงหน้า", baht(self.advance_payment)),
            ("fa-calendar-check", "พร้อมเข้าอยู่", self.move_in_date),
            ("fa-circle-check", "สถานะ", "พร้อมให้บริการ" if self.availability else "ไม่ว่าง/จองแล้ว"),
        ]
        return [{"icon": icon, "label": label, "value": value} for icon, label, value in rows if value not in ("", None)]

    @property
    def price_per_sqm(self):
        return round(self.price / self.size_usable) if self.size_usable else None

    @property
    def price_per_sqwah(self):
        return round(self.price / self.size_land) if self.size_land else None

    @property
    def price_per_rai(self):
        return round(self.price / (self.size_land / 400)) if self.size_land else None

    @property
    def seo_title(self):
        return f"{self.get_property_type_display()}{self.category.name} {self.title} {self.location.name} รหัส {self.property_code}"

    def completeness(self):
        """คะแนนความครบถ้วนของประกาศ เพื่อเตือนแอดมินก่อนเผยแพร่"""
        image_count = self.images.count()
        checks = [
            (10, len(self.title.strip()) >= 10, "ชื่อประกาศอย่างน้อย 10 ตัวอักษร"),
            (10, len(self.description.strip()) >= 30, "รายละเอียดอย่างน้อย 30 ตัวอักษร"),
            (10, bool(self.price), "ราคา"),
            (20, image_count >= settings.MIN_LISTING_IMAGES, f"รูปภาพอย่างน้อย {settings.MIN_LISTING_IMAGES} รูป (มี {image_count} รูป)"),
            (10, bool(self.google_maps_link), "ลิงก์ Google Maps"),
            (10, bool(self.size_land or self.size_usable), "ขนาดที่ดินหรือพื้นที่ใช้สอย"),
            (10, self.bedrooms is not None or self.bathrooms is not None, "จำนวนห้องนอน/ห้องน้ำ"),
            (5, bool(self.direction), "ทิศหน้าทรัพย์"),
            (5, bool(self.common_fee or self.deposit or self.minimum_lease), "ค่าส่วนกลางหรือเงื่อนไขสัญญา"),
            (10, bool(self.feature_list), "จุดเด่นของทรัพย์"),
        ]
        return {
            "score": sum(points for points, passed, _ in checks if passed),
            "missing": [label for _, passed, label in checks if not passed],
        }


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="properties/%Y/%m/")
    thumbnail = models.ImageField(upload_to="properties/%Y/%m/thumbs/", blank=True)
    is_cover = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def card_url(self):
        """รูปย่อสำหรับการ์ด รูปเก่าที่ยังไม่มีรูปย่อใช้รูปเต็มแทน"""
        return (self.thumbnail or self.image).url


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="bookmarked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "property"], name="unique_bookmark")]


class Consignment(models.Model):
    class Type(models.TextChoices):
        HOUSE = "HOUSE", "บ้าน / ทาวน์เฮาส์"
        CONDO = "CONDO", "คอนโด"
        LAND = "LAND", "ที่ดิน"
        WAREHOUSE = "WAREHOUSE", "โรงงาน / โกดัง"
        HOTEL = "HOTEL", "โรงแรม / รีสอร์ต / อพาร์ตเมนต์"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "ยังส่งไม่ครบ"
        PENDING = "PENDING", "รอตรวจสอบ"
        REVIEWED = "REVIEWED", "ตรวจสอบแล้ว"
        APPROVED = "APPROVED", "อนุมัติแล้ว"
        REJECTED = "REJECTED", "ปฏิเสธ"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="consignments")
    owner_name = models.CharField("ชื่อผู้ฝากขาย", max_length=150)
    owner_phone = models.CharField("เบอร์โทรศัพท์", max_length=30)
    owner_line_id = models.CharField("LINE ID", max_length=100, blank=True)
    owner_email = models.EmailField("อีเมล", blank=True)

    property_type = models.CharField("ประเภททรัพย์", max_length=20, choices=Type.choices)
    target_price = models.DecimalField("ราคาที่ต้องการ (บาท)", max_digits=14, decimal_places=2)
    province = models.CharField("จังหวัด", max_length=100)
    district = models.CharField("อำเภอ/เขต", max_length=100)
    subdistrict = models.CharField("ตำบล/แขวง", max_length=100)
    google_maps_link = models.URLField("ลิงก์ Google Maps", max_length=500)
    project_name = models.CharField("ชื่อโครงการ/หมู่บ้าน", max_length=200, blank=True)

    bedrooms = models.PositiveIntegerField("ห้องนอน", null=True, blank=True)
    bathrooms = models.PositiveIntegerField("ห้องน้ำ", null=True, blank=True)
    size_land = models.DecimalField("ขนาดที่ดิน (ตร.ว.)", max_digits=10, decimal_places=2, null=True, blank=True)
    size_usable = models.DecimalField("พื้นที่ใช้สอย (ตร.ม.)", max_digits=10, decimal_places=2, null=True, blank=True)
    floors = models.PositiveIntegerField("จำนวนชั้น", null=True, blank=True)
    parking_spaces = models.PositiveIntegerField("ที่จอดรถ (คัน)", null=True, blank=True)
    floor_level = models.CharField("อยู่ชั้นที่", max_length=20, blank=True)
    land_rai = models.PositiveIntegerField("เนื้อที่ (ไร่)", null=True, blank=True)
    land_ngan = models.PositiveIntegerField("เนื้อที่ (งาน)", null=True, blank=True)
    land_sqw = models.DecimalField("เนื้อที่ (ตารางวา)", max_digits=8, decimal_places=2, null=True, blank=True)
    land_width = models.DecimalField("หน้ากว้างโดยประมาณ (เมตร)", max_digits=8, decimal_places=2, null=True, blank=True)
    road_name = models.CharField("ติดถนนอะไร", max_length=150, blank=True)
    road_width = models.DecimalField("ความกว้างถนน (เมตร)", max_digits=6, decimal_places=2, null=True, blank=True)
    estate_name = models.CharField("นิคมอุตสาหกรรม", max_length=150, blank=True)
    has_license = models.BooleanField("มีใบอนุญาต รง.4 / ใบอนุญาตโกดัง", default=False)
    room_count = models.PositiveIntegerField("จำนวนห้องพักทั้งหมด", null=True, blank=True)
    sell_with_business = models.BooleanField("ขายพร้อมใบอนุญาตและกิจการ", default=False)
    highlights = models.TextField("จุดเด่นทรัพย์", blank=True)
    notes = models.TextField("หมายเหตุ", blank=True)

    status = models.CharField("สถานะ", max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    converted_property = models.ForeignKey(Property, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField("ส่งเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "ฝากขาย"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.owner_name} - {self.get_property_type_display()}"

    @property
    def land_total_sqw(self):
        """รวมเนื้อที่เป็นตารางวา: 1 ไร่ = 400 ตร.ว., 1 งาน = 100 ตร.ว."""
        if self.size_land:
            return self.size_land
        if self.land_rai or self.land_ngan or self.land_sqw:
            return (self.land_rai or 0) * 400 + (self.land_ngan or 0) * 100 + (self.land_sqw or 0)
        return None

    @property
    def spec_rows(self):
        """สเปกที่กรอกมา แสดงในหน้าตรวจสอบของเจ้าหน้าที่"""
        names = [
            "project_name", "size_land", "size_usable", "bedrooms", "bathrooms", "floors", "parking_spaces",
            "floor_level", "land_rai", "land_ngan", "land_sqw", "land_width", "road_name", "road_width",
            "estate_name", "room_count",
        ]
        rows = [(self._meta.get_field(name).verbose_name, getattr(self, name)) for name in names]
        rows = [(label, value) for label, value in rows if value not in ("", None)]
        rows += [(self._meta.get_field(name).verbose_name, "ใช่") for name in ("has_license", "sell_with_business") if getattr(self, name)]
        return rows


class ConsignmentImage(models.Model):
    consignment = models.ForeignKey(Consignment, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="consignments/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class ConsignmentDeed(models.Model):
    consignment = models.ForeignKey(Consignment, on_delete=models.CASCADE, related_name="deeds")
    file = models.FileField(upload_to="deeds/%Y/%m/", storage=PrivateStorage())
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


@receiver(post_delete, sender=PropertyImage)
@receiver(post_delete, sender=ConsignmentImage)
def delete_image_file(sender, instance, **kwargs):
    instance.image.delete(save=False)
    if getattr(instance, "thumbnail", None):
        instance.thumbnail.delete(save=False)


@receiver(post_delete, sender=ConsignmentDeed)
def delete_deed_file(sender, instance, **kwargs):
    instance.file.delete(save=False)
