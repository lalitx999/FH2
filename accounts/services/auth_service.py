from django.contrib.auth import authenticate

from accounts.models import User
from config.throttle import client_ip, hit, is_over, reset

from . import otp_service

LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCK_SECONDS = 15 * 60


class LoginResult:
    SUCCESS = "success"
    NEEDS_VERIFICATION = "needs_verification"
    INVALID = "invalid"
    LOCKED = "locked"


def _login_key(request, email):
    return f"{email}:{client_ip(request)}"


def attempt_login(request, email, password):
    """คืน (ผลลัพธ์, user) จำกัดการเดารหัสตามอีเมลและ IP"""
    key = _login_key(request, email)
    if is_over("login", key, LOGIN_FAILURE_LIMIT):
        return LoginResult.LOCKED, None
    user = authenticate(request, username=email, password=password)
    if user:
        reset("login", key)
        return LoginResult.SUCCESS, user
    pending = User.objects.filter(email=email, is_active=False).first()
    if pending and pending.check_password(password):
        return LoginResult.NEEDS_VERIFICATION, pending
    hit("login", key, LOGIN_FAILURE_LIMIT, LOGIN_LOCK_SECONDS)
    return LoginResult.INVALID, None


def complete_verification(email, code):
    """ตรวจรหัส แล้วเปิดใช้งานบัญชี"""
    otp_service.verify_otp(email, code)
    user = User.objects.get(email=email)
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user


def registration_blocked(request):
    return hit("register", client_ip(request), 10, 60 * 60)
