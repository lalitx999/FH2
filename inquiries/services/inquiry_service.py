import logging

from django.conf import settings
from kombu.exceptions import OperationalError

from accounts.tasks import send_email

logger = logging.getLogger(__name__)


def create_inquiry(form):
    inquiry = form.save()
    _notify_admin(inquiry)
    return inquiry


def _notify_admin(inquiry):
    if not settings.ADMIN_NOTIFICATION_EMAIL:
        return
    about = inquiry.property.property_code if inquiry.property else "ทั่วไป"
    try:
        send_email.delay(
            f"ข้อความติดต่อใหม่จากคุณ {inquiry.name} ({about})",
            f"ชื่อ: {inquiry.name}\nโทร: {inquiry.phone}\nอีเมล: {inquiry.email}\n\n{inquiry.message}",
            [settings.ADMIN_NOTIFICATION_EMAIL],
        )
    except OperationalError:
        # ข้อความบันทึกลง DB แล้ว คิวล่มต้องไม่ทำให้ลูกค้าเห็น error
        logger.exception("ส่งงานแจ้งเตือนข้อความติดต่อเข้าคิวไม่สำเร็จ")
