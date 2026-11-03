from django.conf import settings

from properties.constants import HOME_LOAN_CATEGORIES
from properties.models import Property

MAX_PRICE = 10_000_000_000


def calculator(mode="home", price=None):
    return {"mode": mode, "price": price, **settings.LOAN_DEFAULTS[mode]}


def for_property(prop):
    """เครื่องคำนวณในหน้าทรัพย์ ทรัพย์เช่าไม่มีการกู้ซื้อจึงไม่แสดง"""
    if prop.property_type != Property.Type.SALE:
        return None
    mode = "home" if prop.category.slug in HOME_LOAN_CATEGORIES else "business"
    return calculator(mode, int(prop.price))


def parse_price(value):
    """ราคาจาก query string ถ้าผิดรูปให้เริ่มจากช่องว่าง ไม่ทำให้หน้าเว็บ error"""
    return int(value) if value and value.isascii() and value.isdigit() and 0 < int(value) <= MAX_PRICE else None
