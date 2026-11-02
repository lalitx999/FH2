"""ใช้ตอนพัฒนาในเครื่อง"""
from .base import *  # noqa: F403
from .base import env_list, os

DEBUG = True
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-not-for-production")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
