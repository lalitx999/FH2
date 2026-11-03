import logging
from urllib.parse import unquote, urljoin, urlsplit

import requests

from properties.models import SHORT_MAPS_HOSTS, coords_from_maps_link

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 5


def _is_google_url(url):
    """ลิงก์มาจากผู้ใช้ ต้องไม่ให้เซิร์ฟเวอร์ถูกพาไปเรียกที่อื่น เช่น บริการภายในเครื่อง"""
    parts = urlsplit(url)
    host = parts.hostname or ""
    google = host == "google.com" or host.endswith((".google.com", ".google.co.th"))
    return parts.scheme == "https" and (host in SHORT_MAPS_HOSTS or google)


def coordinates_from_short_link(link):
    """ตามลิงก์ย่อของ Google Maps ทีละขั้นจนเจอพิกัด คืน (lat, lng) หรือ None"""
    url = link or ""
    for _ in range(MAX_REDIRECTS):
        if not _is_google_url(url):
            return None
        try:
            response = requests.get(url, allow_redirects=False, timeout=TIMEOUT_SECONDS, headers={"User-Agent": "curl/8"})
        except requests.RequestException:
            logger.warning("เรียกลิงก์ Google Maps ไม่สำเร็จ", exc_info=True)
            return None
        if not response.is_redirect:
            return None
        url = urljoin(url, response.headers["Location"])
        if coords := coords_from_maps_link(unquote(url)):
            return coords
    return None
