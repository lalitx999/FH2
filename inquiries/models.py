from django.db import models

from properties.models import Property


class Inquiry(models.Model):
    property = models.ForeignKey(Property, on_delete=models.SET_NULL, null=True, blank=True, related_name="inquiries")
    name = models.CharField("ชื่อ", max_length=150)
    email = models.EmailField("อีเมล")
    phone = models.CharField("เบอร์โทรศัพท์", max_length=30)
    message = models.TextField("ข้อความ")
    is_handled = models.BooleanField("ติดต่อกลับแล้ว", default=False)
    created_at = models.DateTimeField("ส่งเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "ข้อความติดต่อ"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.phone})"
