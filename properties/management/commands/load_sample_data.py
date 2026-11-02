import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from properties.models import Category, Location, Property
from reviews.models import Article

DATA_DIR = Path(__file__).resolve().parents[2]
DATA_FILE = DATA_DIR / "sample_data.json"
PATTAYA_FILE = DATA_DIR / "sample_data_pattaya.json"


class Command(BaseCommand):
    help = "นำเข้าบทความและทรัพย์ตัวอย่างจากเว็บเดิม ใช้ --pattaya เพื่อนำเข้าเฉพาะทรัพย์จำลองโซนพัทยา ใช้ --remove เพื่อลบทรัพย์ตัวอย่าง"

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="ลบทรัพย์ตัวอย่างทั้งหมด (บทความยังอยู่)")
        parser.add_argument("--pattaya", action="store_true", help="นำเข้าเฉพาะทรัพย์จำลองโซนพัทยา")

    @transaction.atomic
    def handle(self, *args, remove=False, pattaya=False, **options):
        if remove:
            count = 0
            for prop in Property.objects.filter(is_sample=True):
                prop.delete()
                count += 1
            self._remove_empty_pattaya_locations()
            self.stdout.write(f"ลบทรัพย์ตัวอย่าง {count} รายการ")
            return

        data = json.loads((PATTAYA_FILE if pattaya else DATA_FILE).read_text(encoding="utf-8"))
        for row in data.get("locations", []):
            Location.objects.get_or_create(slug=row["slug"], defaults={"name": row["name"]})
        added = sum(self._add_property(row) for row in data["properties"])
        articles = sum(self._add_article(row) for row in data.get("articles", []))
        self.stdout.write(f"เพิ่มทรัพย์ตัวอย่าง {added} รายการ บทความ {articles} เรื่อง")

    def _remove_empty_pattaya_locations(self):
        slugs = [row["slug"] for row in json.loads(PATTAYA_FILE.read_text(encoding="utf-8"))["locations"]]
        Location.objects.filter(slug__in=slugs).exclude(pk__in=Property.objects.values("location")).delete()

    def _add_property(self, row):
        if Property.objects.filter(property_code=row["property_code"]).exists():
            return 0
        features = row.pop("features", None) or {}
        for name in ("direction", "furniture", "minimum_lease", "move_in_date"):
            row[name] = row.get(name) or ""
        Property.objects.create(
            category=Category.objects.get(slug=row.pop("category")),
            location=Location.objects.get(slug=row.pop("location")),
            features=[key for key, value in features.items() if value],
            status=Property.Status.PUBLISHED,
            is_sample=True,
            **row,
        )
        return 1

    def _add_article(self, row):
        _, created = Article.objects.get_or_create(slug=row["slug"], defaults={**row, "is_published": True})
        return int(created)
