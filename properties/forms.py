from django import forms

from config.forms import BootstrapFormMixin

from .constants import (
    CATEGORY_FIELDS, FEATURE_CHOICES, LAND_INPUTS, RENT_ONLY_FIELDS, SALE_ONLY_FIELDS, SUB_TYPE_CHOICES, ZONING_CHOICES,
)
from .models import Category, Consignment, Location, Property, split_sqw, total_sqw

# ช่องที่ขึ้นกับหมวด บางหมวดเท่านั้นที่ใช้
CATEGORY_SPECIFIC = {name for names in CATEGORY_FIELDS.values() for name in names}


def categories_with(name):
    return ",".join(slug for slug, names in CATEGORY_FIELDS.items() if name in names)


class SearchForm(BootstrapFormMixin, forms.Form):
    SORTS = [("new", "ล่าสุด"), ("price_asc", "ราคาน้อยไปมาก"), ("price_desc", "ราคามากไปน้อย")]

    q = forms.CharField(label="คำค้นหา", required=False, widget=forms.TextInput(attrs={"placeholder": "ค้นหาชื่อทรัพย์ ทำเล จังหวัด หรือรหัสทรัพย์ (เช่น คอนโด, C0001, ราชบุรี)"}))
    type = forms.ChoiceField(label="ประเภท", required=False, choices=[("", "ขายและเช่า"), *Property.Type.choices])
    category = forms.ModelChoiceField(
        label="หมวดหมู่", required=False, queryset=Category.objects.all(), to_field_name="slug", empty_label="ทุกหมวดหมู่",
        widget=forms.Select(attrs={"data-field-switch": "", "data-show-empty": ""}),
    )
    location = forms.ModelChoiceField(label="ทำเล", required=False, queryset=Location.objects.all(), to_field_name="slug", empty_label="ทุกทำเล")
    province = forms.ChoiceField(label="จังหวัด", required=False)
    price_min = forms.DecimalField(label="ราคาต่ำสุด", required=False, min_value=0, widget=forms.NumberInput(attrs={"placeholder": "ต่ำสุด"}))
    price_max = forms.DecimalField(label="ราคาสูงสุด", required=False, min_value=0, widget=forms.NumberInput(attrs={"placeholder": "สูงสุด"}))
    bedrooms = forms.IntegerField(label="ห้องนอนขั้นต่ำ", required=False, min_value=0)
    sub_type = forms.ChoiceField(label="ประเภทย่อย", required=False, choices=[("", "ทุกประเภทย่อย"), *SUB_TYPE_CHOICES])
    zoning = forms.ChoiceField(label="ผังสี", required=False, choices=[("", "ทุกผังสี"), *ZONING_CHOICES])
    sort = forms.ChoiceField(label="เรียงตาม", required=False, choices=SORTS)

    def __init__(self, *args, provinces=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["province"].choices = [("", "ทุกจังหวัด"), *((name, name) for name in provinces)]
        # ตัวกรองที่มีความหมายเฉพาะบางหมวด
        self.show_for = {name: categories_with(name) for name in ("bedrooms", "sub_type", "zoning")}


class LandmarksField(forms.CharField):
    """กรอกบรรทัดละสถานที่ รูปแบบ ชื่อสถานที่ | ระยะทาง เก็บใน DB เป็นรายการ"""

    widget = forms.Textarea(attrs={"rows": 3, "placeholder": "BTS ทองหล่อ | 450 เมตร"})

    def prepare_value(self, value):
        if isinstance(value, list):
            return "\n".join(f"{item.get('name', '')} | {item.get('distance', '')}".rstrip(" |") for item in value)
        return value

    def clean(self, value):
        landmarks = []
        for line in (value or "").splitlines():
            name, _, distance = line.partition("|")
            if name.strip():
                landmarks.append({"name": name.strip(), "distance": distance.strip()})
        return landmarks


class CategorySelect(forms.Select):
    """ค่าใน select ยังเป็น pk เหมือนเดิม แต่บอก slug ให้ JS เลือกช่องที่จะแสดง"""

    def create_option(self, name, value, *args, **kwargs):
        option = super().create_option(name, value, *args, **kwargs)
        if value:
            option["attrs"]["data-slug"] = value.instance.slug
        return option


class PropertyExtrasMixin(forms.Form):
    features = forms.MultipleChoiceField(label="คุณสมบัติ", required=False, choices=FEATURE_CHOICES, widget=forms.CheckboxSelectMultiple)
    landmarks = LandmarksField(label="สถานที่ใกล้เคียง", required=False, help_text="บรรทัดละ 1 แห่ง รูปแบบ ชื่อสถานที่ | ระยะทาง")
    land_rai = forms.IntegerField(label="เนื้อที่ (ไร่)", required=False, min_value=0)
    land_ngan = forms.IntegerField(label="เนื้อที่ (งาน)", required=False, min_value=0, max_value=3)
    land_sqw = forms.DecimalField(
        label="เนื้อที่ (ตร.ว.)", required=False, min_value=0, max_value=99.99, decimal_places=2,
        help_text='<span data-land-total>รวม - ตร.ว.</span> ไม่เกิน 3 งาน และ 99.99 ตร.ว. ต่อช่อง',
    )

    SECTIONS = [
        ("ข้อมูลหลัก", "fa-file-lines", ["title", "property_type", "category", "sub_type", "reference_code", "location", "project_name", "price", "description"]),
        ("ที่ตั้ง", "fa-location-dot", ["province", "district", "subdistrict", "road_name", "road_width", "google_maps_link", "latitude", "longitude", "landmarks"]),
        ("ขนาดและอาคาร", "fa-ruler-combined", [
            *LAND_INPUTS, "size_usable", "land_width", "land_depth", "zoning", "building_count", "unit_count", "room_count",
            "bedrooms", "bathrooms", "floors", "floor_level", "parking_spaces", "direction", "furniture", "estate_name",
            "has_license", "sell_with_business",
        ]),
        ("ราคาและเงื่อนไข", "fa-coins", [
            "sale_condition", "rent_price", "transfer_fee", "common_fee", "deposit", "advance_payment", "minimum_lease",
            "move_in_date", "pet_friendly",
        ]),
        ("จุดเด่น", "fa-star", ["features"]),
        ("ผู้ขาย", "fa-user", ["seller_name", "seller_phone", "seller_line_id", "is_direct_seller"]),
        ("ข้อมูลภายใน", "fa-lock", ["status", "source", "agent", "availability"]),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["size_land"].widget = forms.HiddenInput()
        self.fields["category"].widget = CategorySelect(attrs={"data-field-switch": ""})
        self.fields["category"].widget.choices = self.fields["category"].choices
        # มีค่าเริ่มต้นอยู่แล้ว และถูกซ่อนเมื่อเป็นประกาศเช่า
        self.fields["sale_condition"].required = False
        if self.instance.size_land:
            rai, ngan, sqw = split_sqw(self.instance.size_land)
            self.initial.update(land_rai=rai, land_ngan=ngan, land_sqw=sqw)

    def _known_slugs(self):
        return [category.slug for category in self.fields["category"].queryset]

    def _show_for(self, name, slugs):
        if name not in CATEGORY_SPECIFIC:
            return ""
        # หมวดที่สร้างเองในหลังบ้านยังไม่มีกฎ จึงแสดงทุกช่องให้กรอกได้
        return ",".join(slug for slug in slugs if slug not in CATEGORY_FIELDS or name in CATEGORY_FIELDS[slug])

    def _show_type(self, name):
        if name in RENT_ONLY_FIELDS:
            return Property.Type.RENT
        return Property.Type.SALE if name in SALE_ONLY_FIELDS else ""

    def sections(self):
        slugs = self._known_slugs()
        return [
            {
                "title": title,
                "icon": icon,
                "fields": [
                    {"field": self[name], "show_for": self._show_for(name, slugs), "show_type": self._show_type(name)}
                    for name in names if name in self.fields
                ],
            }
            for title, icon, names in self.SECTIONS
            if any(name in self.fields for name in names)
        ]

    def _applies(self, name, category, property_type):
        if name in RENT_ONLY_FIELDS and property_type != Property.Type.RENT:
            return False
        if name in SALE_ONLY_FIELDS and property_type != Property.Type.SALE:
            return False
        if name in CATEGORY_SPECIFIC and category and category.slug in CATEGORY_FIELDS:
            return name in CATEGORY_FIELDS[category.slug]
        return True

    def clean(self):
        cleaned = super().clean()
        category, property_type = cleaned.get("category"), cleaned.get("property_type")
        for name in [*CATEGORY_SPECIFIC, *RENT_ONLY_FIELDS, *SALE_ONLY_FIELDS]:
            if name not in self.fields or self._applies(name, category, property_type):
                continue
            # ช่องที่ซ่อนอยู่ต้องไม่ค้างค่าเดิม และต้องไม่ทำให้บันทึกไม่ผ่าน
            self.errors.pop(name, None)
            cleaned[name] = None if name in LAND_INPUTS else Property._meta.get_field(name).get_default()
        cleaned["size_land"] = total_sqw(cleaned.get("land_rai"), cleaned.get("land_ngan"), cleaned.get("land_sqw"))
        return cleaned


class ListingForm(BootstrapFormMixin, PropertyExtrasMixin, forms.ModelForm):
    """ฟอร์มลงประกาศของผู้ใช้ทั่วไป ไม่มีช่องสถานะ ผู้ใช้จึงเผยแพร่เองไม่ได้"""

    class Meta:
        model = Property
        fields = [
            "title", "property_type", "category", "sub_type", "location", "project_name", "price", "description",
            "province", "district", "subdistrict", "road_name", "road_width", "google_maps_link",
            "size_land", "size_usable", "land_width", "land_depth", "zoning", "building_count", "unit_count", "room_count",
            "bedrooms", "bathrooms", "floors", "floor_level", "parking_spaces", "direction", "furniture", "estate_name",
            "has_license", "sell_with_business",
            "sale_condition", "rent_price", "transfer_fee", "common_fee", "deposit", "advance_payment", "minimum_lease",
            "move_in_date", "pet_friendly",
            "features", "landmarks",
            "seller_name", "seller_phone", "seller_line_id",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["seller_name"].required = True
        self.fields["seller_phone"].required = True


class ConsignmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Consignment
        fields = [
            "owner_name", "owner_phone", "owner_line_id", "owner_email",
            "property_type", "target_price", "province", "district", "subdistrict", "google_maps_link", "project_name",
            "size_land", "size_usable", "bedrooms", "bathrooms", "floors", "parking_spaces", "floor_level",
            "land_rai", "land_ngan", "land_sqw", "land_width", "road_name", "road_width",
            "estate_name", "has_license", "room_count", "sell_with_business", "highlights", "notes",
        ]
        widgets = {"highlights": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3})}

    STEPS = [
        ("ข้อมูลผู้ฝากขาย", "fa-user", ["owner_name", "owner_phone", "owner_line_id", "owner_email"]),
        ("ข้อมูลทรัพย์", "fa-house", ["property_type", "target_price", "province", "district", "subdistrict", "google_maps_link", "project_name"]),
        ("รายละเอียด", "fa-list-check", [
            "size_land", "size_usable", "bedrooms", "bathrooms", "floors", "parking_spaces", "floor_level",
            "land_rai", "land_ngan", "land_sqw", "land_width", "road_name", "road_width",
            "estate_name", "has_license", "room_count", "sell_with_business", "highlights", "notes",
        ]),
    ]

    # ช่องที่แสดงเฉพาะบางประเภททรัพย์ ช่องที่ไม่อยู่ในนี้แสดงทุกประเภท
    SHOW_FOR = {
        "size_land": "HOUSE,WAREHOUSE,HOTEL",
        "size_usable": "HOUSE,CONDO,WAREHOUSE",
        "bedrooms": "HOUSE,CONDO",
        "bathrooms": "HOUSE,CONDO",
        "floors": "HOUSE,HOTEL",
        "parking_spaces": "HOUSE",
        "floor_level": "CONDO",
        "land_rai": "LAND",
        "land_ngan": "LAND",
        "land_sqw": "LAND",
        "land_width": "LAND",
        "road_name": "LAND",
        "road_width": "LAND",
        "estate_name": "WAREHOUSE",
        "has_license": "WAREHOUSE",
        "room_count": "HOTEL",
        "sell_with_business": "HOTEL",
    }

    def steps(self):
        return [
            {
                "title": title,
                "icon": icon,
                "fields": [{"field": self[name], "show_for": self.SHOW_FOR.get(name, "")} for name in names],
            }
            for title, icon, names in self.STEPS
        ]
