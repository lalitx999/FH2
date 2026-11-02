from django.db import migrations

CATEGORIES = [
    ("house", "บ้านเดี่ยว / พูลวิลล่า", "H"),
    ("condo", "คอนโดมิเนียม", "C"),
    ("land", "ที่ดิน", "L"),
    ("townhome", "ทาวน์โฮม / ทาวน์เฮาส์", "H"),
    ("commercial", "อาคารพาณิชย์ / ตึกแถว", "B"),
    ("warehouse", "โกดัง / โรงงาน", "W"),
    ("hotel", "โรงแรม / รีสอร์ท", "T"),
]
OLD_SEED_LOCATIONS = ["bangkok", "phuket", "chiangmai", "pattaya"]
LOCATIONS = [
    ("sukhumvit-thonglor", "สุขุมวิท - ทองหล่อ"),
    ("sathorn-silom", "สาทร - สีลม"),
    ("aree-phayathai", "อารีย์ - พญาไท"),
    ("rama9-ratchada", "พระราม 9 - รัชดา"),
    ("bangna-srinakarin", "บางนา - ศรีนครินทร์"),
    ("ekkamai-phra-khanong", "เอกมัย - พระโขนง"),
    ("ratchapruek-pinklao", "ราชพฤกษ์ - ปิ่นเกล้า"),
    ("chaengwattana-pakkret", "แจ้งวัฒนะ - ปากเกร็ด"),
    ("ramintra-praditmanutham", "รามอินทรา - ประดิษฐ์มนูธรรม"),
    ("pathumwan-siam", "ปทุมวัน - สยาม"),
    ("ladprao-chokchai4", "ลาดพร้าว - โชคชัย 4"),
    ("bangsue-taopoon", "บางซื่อ - เตาปูน"),
    ("huamark-ramkhamhaeng", "หัวหมาก - รามคำแหง"),
    ("rama2-saemdam", "พระราม 2 - แสมดำ"),
    ("talingchan-phutthamonthon", "ตลิ่งชัน - พุทธมณฑล"),
]


def apply(apps, schema_editor):
    Category = apps.get_model("properties", "Category")
    Location = apps.get_model("properties", "Location")
    for order, (slug, name, prefix) in enumerate(CATEGORIES):
        Category.objects.update_or_create(slug=slug, defaults={"name": name, "code_prefix": prefix, "sort_order": order})
    Location.objects.filter(slug__in=OLD_SEED_LOCATIONS, properties__isnull=True).delete()
    for slug, name in LOCATIONS:
        Location.objects.update_or_create(slug=slug, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("properties", "0003_alter_category_options_category_sort_order_and_more")]
    operations = [migrations.RunPython(apply, migrations.RunPython.noop)]
