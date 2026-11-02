"""ข้อตกลง Ajax ของทั้งเว็บ (ฝั่ง JS อยู่ที่ static/js/app.js)

สำเร็จ    2xx  ส่ง HTML กลับไปแทนที่เป้าหมาย
ฟอร์มผิด  422  ส่ง HTML ของฟอร์มพร้อม error กลับไปแทนที่เดิม
ผิดพลาด   4xx  ส่งข้อความล้วน แสดงเป็น toast
ไม่ login 401  ส่ง header X-Login-URL แล้ว JS พาไปหน้า login
"""
from functools import wraps

from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.conf import settings


def is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def error(message, status=400):
    return HttpResponse(message, status=status, content_type="text/plain; charset=utf-8")


def ajax_login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            response = HttpResponse("กรุณาเข้าสู่ระบบ", status=401, content_type="text/plain; charset=utf-8")
            response["X-Login-URL"] = resolve_url(settings.LOGIN_URL)
            return response
        return view(request, *args, **kwargs)

    return wrapper
