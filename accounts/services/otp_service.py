import logging
import secrets
from datetime import timedelta

from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from kombu.exceptions import OperationalError

from accounts.models import EmailOTP
from accounts.tasks import send_email

logger = logging.getLogger(__name__)

VALID_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
MAX_SENDS_PER_HOUR = 5


class OTPError(Exception):
    """ข้อความใน exception นี้แสดงให้ผู้ใช้เห็นได้"""


def _hash(email, code):
    return salted_hmac("accounts.otp", f"{email}:{code}").hexdigest()


def send_otp(email):
    now = timezone.now()
    recent = EmailOTP.objects.filter(email=email, created_at__gte=now - timedelta(hours=1))
    latest = recent.first()
    if latest and (now - latest.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
        raise OTPError(f"กรุณารอ {RESEND_COOLDOWN_SECONDS} วินาทีก่อนขอรหัสใหม่")
    if recent.count() >= MAX_SENDS_PER_HOUR:
        raise OTPError("ขอรหัสบ่อยเกินไป กรุณาลองใหม่ภายหลัง")

    code = f"{secrets.randbelow(1_000_000):06d}"
    otp = EmailOTP.objects.create(
        email=email,
        code_hash=_hash(email, code),
        expires_at=now + timedelta(minutes=VALID_MINUTES),
    )
    body = f"รหัส OTP ของคุณคือ {code}\n\nรหัสมีอายุ {VALID_MINUTES} นาที หากคุณไม่ได้เป็นผู้ขอ กรุณาเพิกเฉยต่ออีเมลฉบับนี้"
    try:
        send_email.delay("รหัสยืนยันตัวตน Finding House", body, [email])
    except OperationalError:
        logger.exception("ส่งงานอีเมล OTP เข้าคิวไม่สำเร็จ")
        otp.delete()
        raise OTPError("ส่งอีเมลไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")


def verify_otp(email, code):
    otp = EmailOTP.objects.filter(email=email, is_used=False).first()
    if not otp or timezone.now() > otp.expires_at:
        raise OTPError("รหัสหมดอายุแล้ว กรุณาขอรหัสใหม่")
    if otp.attempts >= MAX_ATTEMPTS:
        raise OTPError("กรอกรหัสผิดเกินจำนวนครั้ง กรุณาขอรหัสใหม่")
    if not constant_time_compare(otp.code_hash, _hash(email, code.strip())):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise OTPError("รหัสไม่ถูกต้อง")
    otp.is_used = True
    otp.save(update_fields=["is_used"])
