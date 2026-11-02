from django import forms

from config.forms import BootstrapFormMixin

from .constants import FEATURE_CHOICES
from .models import Category, Consignment, Location, Property


class SearchForm(BootstrapFormMixin, forms.Form):
    SORTS = [("new", "ล่าสุด"), ("price_asc", "ราคาน้อยไปมาก"), ("price_desc", "ราคามากไปน้อย")]

    q = forms.CharField(label="คำค้นหา", required=False, widget=forms.TextInput(attrs={"placeholder": "ค้นหาชื่อทรัพย์ ทำเล หรือรหัสทรัพย์ (เช่น คอนโด, C0001, ทองหล่อ)"}))
    type = forms.ChoiceField(label="ประเภท", required=False, choices=[("", "ขายและเช่า"), *Property.Type.choices])
    category = forms.ModelChoiceField(label="หมวดหมู่", required=False, queryset=Category.objects.all(), to_field_name="slug", empty_label="ทุกหมวดหมู่")
    location = forms.ModelChoiceField(label="ทำเล", required=False, queryset=Location.objects.all(), to_field_name="slug", empty_label="ทุกทำเล")
    price_min = forms.DecimalField(label="ราคาต่ำสุด", required=False, min_value=0, widget=forms.NumberInput(attrs={"placeholder": "ต่ำสุด"}))
    price_max = forms.DecimalField(label="ราคาสูงสุด", required=False, min_value=0, widget=forms.NumberInput(attrs={"placeholder": "สูงสุด"}))
    bedrooms = forms.IntegerField(label="ห้องนอนขั้นต่ำ", required=False, min_value=0)
    sort = forms.ChoiceField(label="เรียงตาม", required=False, choices=SORTS)


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


class PropertyExtrasMixin(forms.Form):
    features = forms.MultipleChoiceField(label="คุณสมบัติ", required=False, choices=FEATURE_CHOICES, widget=forms.CheckboxSelectMultiple)
    landmarks = LandmarksField(label="สถานที่ใกล้เคียง", required=False, help_text="บรรทัดละ 1 แห่ง รูปแบบ ชื่อสถานที่ | ระยะทาง")


class ListingForm(BootstrapFormMixin, PropertyExtrasMixin, forms.ModelForm):
    """ฟอร์มลงประกาศของผู้ใช้ทั่วไป ไม่มีช่องสถานะ ผู้ใช้จึงเผยแพร่เองไม่ได้"""

    class Meta:
        model = Property
        fields = [
            "title", "property_type", "category", "location", "price", "description",
            "bedrooms", "bathrooms", "floors", "parking_spaces", "size_land", "size_usable", "direction", "furniture",
            "features", "landmarks", "google_maps_link",
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
