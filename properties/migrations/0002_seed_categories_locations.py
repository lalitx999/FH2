from django.db import migrations

CATEGORIES = [
    ("บ้าน / ทาวน์โฮม", "house", "H"),
    ("คอนโด", "condo", "C"),
    ("ที่ดิน", "land", "L"),
    ("โรงงาน / โกดัง", "warehouse", "W"),
    ("โรงแรม / อพาร์ตเมนต์", "hotel", "T"),
]
LOCATIONS = [
    ("กรุงเทพมหานคร", "bangkok"),
    ("ภูเก็ต", "phuket"),
    ("เชียงใหม่", "chiangmai"),
    ("พัทยา", "pattaya"),
]


def seed(apps, schema_editor):
    Category = apps.get_model("properties", "Category")
    Location = apps.get_model("properties", "Location")
    for name, slug, prefix in CATEGORIES:
        Category.objects.get_or_create(slug=slug, defaults={"name": name, "code_prefix": prefix})
    for name, slug in LOCATIONS:
        Location.objects.get_or_create(slug=slug, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("properties", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
