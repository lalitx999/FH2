"""จำกัดความถี่ของคำขอสาธารณะ ใช้ cache จึงทำงานข้าม worker เมื่อใช้ Redis

Redis ล่มต้องไม่ทำให้เว็บล่มไปด้วย จึงปล่อยผ่านและบันทึก log
"""
import logging

from django.conf import settings
from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def client_ip(request):
    header = settings.CLIENT_IP_HEADER
    return (header and request.META.get(header)) or request.META.get("REMOTE_ADDR", "")


def _key(scope, identity):
    return f"throttle:{scope}:{identity}"


def hit(scope, identity, limit, window_seconds):
    """นับคำขอหนึ่งครั้ง คืน True เมื่อเกินโควตา"""
    key = _key(scope, identity)
    try:
        cache.add(key, 0, window_seconds)
        try:
            return cache.incr(key) > limit
        except ValueError:  # key หมดอายุระหว่างทาง
            cache.set(key, 1, window_seconds)
            return False
    except RedisError:
        logger.exception("ตรวจโควตา %s ไม่ได้", scope)
        return False


def is_over(scope, identity, limit):
    """ดูโควตาโดยไม่นับเพิ่ม"""
    try:
        return cache.get(_key(scope, identity), 0) >= limit
    except RedisError:
        logger.exception("ตรวจโควตา %s ไม่ได้", scope)
        return False


def reset(scope, identity):
    try:
        cache.delete(_key(scope, identity))
    except RedisError:
        logger.exception("ล้างโควตา %s ไม่ได้", scope)
