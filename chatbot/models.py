import uuid

from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="ผู้ใช้", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="chat_sessions",
    )
    created_at = models.DateTimeField("เริ่มเมื่อ", auto_now_add=True)
    updated_at = models.DateTimeField("ล่าสุด", auto_now=True)

    class Meta:
        verbose_name = "บทสนทนา"
        ordering = ["-updated_at"]


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "ผู้ใช้"
        ASSISTANT = "assistant", "ผู้ช่วย"

    class Status(models.TextChoices):
        PENDING = "pending", "กำลังตอบ"
        DONE = "done", "ตอบแล้ว"
        FAILED = "failed", "ไม่สำเร็จ"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DONE)
    provider = models.CharField("ผู้ให้บริการที่ตอบ", max_length=20, blank=True)
    suggestions = models.ManyToManyField("properties.Property", blank=True, related_name="+")
    actions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ข้อความแชท"
        ordering = ["created_at", "id"]
