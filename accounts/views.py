from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from config.ajax import error

from .forms import LoginForm, ProfileForm, RegisterForm, VerifyForm
from .services import auth_service
from .services.auth_service import LoginResult
from .services.otp_service import OTPError, send_otp

BACKEND = "django.contrib.auth.backends.ModelBackend"


def _start_verification(request, email):
    """เก็บอีเมลที่รอยืนยันไว้ใน session แล้วส่งรหัส"""
    request.session["pending_email"] = email
    try:
        send_otp(email)
    except OTPError as exc:
        messages.warning(request, str(exc))
    return redirect("accounts:verify_email")


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return ""


def login_view(request):
    if request.user.is_authenticated:
        return redirect("pages:home")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        result, user = auth_service.attempt_login(request, email, form.cleaned_data["password"])
        if result == LoginResult.SUCCESS:
            login(request, user)
            return redirect(_safe_next(request) or ("dashboard:home" if user.is_staff else "pages:home"))
        if result == LoginResult.NEEDS_VERIFICATION:
            messages.info(request, "กรุณายืนยันอีเมลก่อนเข้าสู่ระบบ")
            return _start_verification(request, email)
        form.add_error(None, "ลองผิดหลายครั้งเกินไป กรุณารอ 15 นาทีแล้วลองใหม่" if result == LoginResult.LOCKED else "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    return render(request, "accounts/login.html", {"form": form, "next": _safe_next(request)})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("pages:home")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("pages:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        if auth_service.registration_blocked(request):
            messages.error(request, "สมัครบ่อยเกินไป กรุณาลองใหม่ภายหลัง")
        elif form.is_valid():
            user = form.save()
            return _start_verification(request, user.email)
    return render(request, "accounts/register.html", {"form": form})


def verify_email_view(request):
    email = request.session.get("pending_email")
    if not email:
        return redirect("accounts:login")
    form = VerifyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = auth_service.complete_verification(email, form.cleaned_data["code"])
        except OTPError as exc:
            form.add_error("code", str(exc))
        else:
            del request.session["pending_email"]
            login(request, user, backend=BACKEND)
            messages.success(request, "ยืนยันอีเมลเรียบร้อย ยินดีต้อนรับครับ")
            return redirect("pages:home")
    return render(request, "accounts/verify_email.html", {"form": form, "email": email})


@require_POST
def resend_otp_view(request):
    email = request.session.get("pending_email")
    if not email:
        return error("ไม่พบอีเมลที่รอยืนยัน")
    try:
        send_otp(email)
    except OTPError as exc:
        return error(str(exc), status=429)
    return HttpResponse('<span class="text-success"><i class="fa-solid fa-circle-check me-1"></i>ส่งรหัสใหม่แล้ว</span>')


@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "บันทึกข้อมูลแล้ว")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
