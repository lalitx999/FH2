from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from properties.models import Property, unique_slug


class Article(models.Model):
    class Kind(models.TextChoices):
        ARTICLE = "ARTICLE", "บทความ"
        REVIEW = "REVIEW", "รีวิวทรัพย์"

    kind = models.CharField("ประเภท", max_length=10, choices=Kind.choices, default=Kind.ARTICLE)
    category = models.CharField("หมวดบทความ", max_length=100, default="ความรู้เรื่องบ้าน")
    title = models.CharField("หัวข้อ", max_length=250)
    slug = models.SlugField(max_length=260, unique=True, allow_unicode=True, blank=True, editable=False)
    cover_image = models.ImageField("รูปหน้าปก", upload_to="articles/", null=True, blank=True)
    excerpt = models.TextField("สรุปย่อ", blank=True)
    content = models.TextField("เนื้อหา")
    property = models.ForeignKey(Property, verbose_name="ทรัพย์ที่เกี่ยวข้อง", on_delete=models.SET_NULL, null=True, blank=True, related_name="articles")
    is_published = models.BooleanField("เผยแพร่", default=False)
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)
    updated_at = models.DateTimeField("แก้ไขล่าสุด", auto_now=True)

    class Meta:
        verbose_name = "บทความ"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Article, self.title, self.pk, 260)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        name = "reviews:review_detail" if self.kind == self.Kind.REVIEW else "reviews:article_detail"
        return reverse(name, args=[self.slug])


class CustomerReview(models.Model):
    reviewer_name = models.CharField("ชื่อผู้รีวิว", max_length=120)
    rating = models.PositiveSmallIntegerField("คะแนน (1-5)", default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField("ความคิดเห็น")
    is_approved = models.BooleanField("อนุมัติแล้ว", default=False)
    created_at = models.DateTimeField("ส่งเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "รีวิวลูกค้า"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reviewer_name} ({self.rating})"

    @property
    def stars(self):
        return range(self.rating)
