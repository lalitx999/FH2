import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "accounts",
    "pages",
    "properties",
    "inquiries",
    "reviews",
    "dashboard",
    "chatbot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ค่าเริ่มต้นของ Django คือ same-origin ซึ่งไม่ส่ง Referer ไปเว็บอื่น ทำให้ OpenStreetMap บล็อกภาพแผนที่
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context.site",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "fh_app"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "pages:home"
LOGOUT_REDIRECT_URL = "pages:home"

LANGUAGE_CODE = "th"
TIME_ZONE = "Asia/Bangkok"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static", ("bootstrap", BASE_DIR / "bootstrap-5.3.8-dist")]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# เอกสารลับ (โฉนด) อยู่นอก MEDIA_ROOT เปิดได้ผ่าน view ที่ตรวจสิทธิ์เท่านั้น
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# อีเมล: Hostinger ใช้ SSL พอร์ต 465
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.hostinger.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USE_SSL = EMAIL_PORT == 465
EMAIL_USE_TLS = EMAIL_PORT == 587
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = 10
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_USER
    else "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "noreply@localhost"
ADMIN_NOTIFICATION_EMAIL = os.getenv("ADMIN_NOTIFICATION_EMAIL") or EMAIL_HOST_USER

# ข้อมูลติดต่อบนเว็บ
SITE_PHONE = os.getenv("SITE_PHONE", "")
SITE_EMAIL = os.getenv("SITE_EMAIL", "")
SITE_LINE_ID = os.getenv("SITE_LINE_ID", "")
SITE_LINE_URL = os.getenv("SITE_LINE_URL", "")

# กฎการลงทรัพย์ อยู่ที่เดียว
MIN_LISTING_IMAGES = 20
MAX_LISTING_IMAGES = 30
MAX_DEED_FILES = 10
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_COMPARE_ITEMS = 4

# ค่าเริ่มต้นเครื่องคำนวณสินเชื่อ เป็นค่าตัวอย่าง ไม่ใช่อัตราของธนาคารใด ผู้ใช้แก้เองได้บนหน้าเว็บ
LOAN_DEFAULTS = {
    "home": {
        "rate": float(os.getenv("LOAN_HOME_RATE", "6")),
        "years": int(os.getenv("LOAN_HOME_YEARS", "30")),
        "down_percent": float(os.getenv("LOAN_HOME_DOWN_PERCENT", "10")),
        "income_ratio": float(os.getenv("LOAN_HOME_INCOME_RATIO", "40")),
    },
    "business": {
        "rate": float(os.getenv("LOAN_BUSINESS_RATE", "7.5")),
        "years": int(os.getenv("LOAN_BUSINESS_YEARS", "10")),
        "down_percent": float(os.getenv("LOAN_BUSINESS_DOWN_PERCENT", "30")),
    },
}

# Celery: งานช้าทั้งหมด (อีเมล, เรียก API ภายนอก, AI, แปลงฝากขาย) ทำเบื้องหลัง
REDIS_URL = os.getenv("REDIS_URL", "")
CELERY_BROKER_URL = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL  # ไม่มี Redis ให้ทำทันทีในโปรเซสเดียว ใช้ตอนพัฒนาในเครื่อง
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 120
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
        if REDIS_URL
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    )
}

# header ที่ reverse proxy ใส่ IP จริงของผู้ใช้ เว้นว่างคือใช้ REMOTE_ADDR
CLIENT_IP_HEADER = os.getenv("CLIENT_IP_HEADER", "")

# แชทบอท: ลองตามลำดับใน LLM_PROVIDERS ถ้าใช้ไม่ได้ทั้งหมดจะตอบด้วยกฎพื้นฐาน
LLM_PROVIDERS = env_list("LLM_PROVIDERS")
LLM_TIMEOUT_SECONDS = 30
LLM_CONFIG = {
    "local": {
        "base_url": os.getenv("LLM_LOCAL_BASE_URL", ""),
        "api_key": os.getenv("LLM_LOCAL_API_KEY", ""),
        "model": os.getenv("LLM_LOCAL_MODEL", ""),
    },
    "claude": {
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "model": os.getenv("LLM_CLAUDE_MODEL", "claude-opus-5-5"),
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "model": os.getenv("LLM_DEEPSEEK_MODEL", ""),
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY", ""),
        "model": os.getenv("LLM_GROQ_MODEL", ""),
    },
    "gemini": {
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "model": os.getenv("LLM_GEMINI_MODEL", ""),
    },
}
CHAT_MAX_MESSAGE_LENGTH = 500

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
