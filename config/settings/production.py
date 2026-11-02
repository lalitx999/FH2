"""ใช้บนเซิร์ฟเวอร์จริง ค่าที่ขาดจะหยุดตั้งแต่ตอนเริ่ม ไม่ปล่อยให้ระบบรันแบบไม่ปลอดภัย"""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import REDIS_URL, env_list, os

DEBUG = False


def required(name):
    value = os.getenv(name, "")
    if not value:
        raise ImproperlyConfigured(f"ต้องตั้งค่า {name} ใน .env")
    return value


SECRET_KEY = required("SECRET_KEY")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or [required("ALLOWED_HOSTS")]
if not REDIS_URL:
    raise ImproperlyConfigured("ต้องตั้งค่า REDIS_URL ใน .env เพื่อให้ Celery ทำงานเบื้องหลัง")

# บีบอัด HTML ต่อจาก WhiteNoise ส่วน static มีไฟล์บีบอัดอยู่แล้ว
whitenoise_index = MIDDLEWARE.index("whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
MIDDLEWARE.insert(whitenoise_index + 1, "django.middleware.gzip.GZipMiddleware")  # noqa: F405

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# HTTPS จบที่ Cloudflare แล้วส่งต่อเข้ามาเป็น HTTP
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True") == "True"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "86400"))
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
