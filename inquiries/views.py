from django.shortcuts import render
from django.views.decorators.http import require_POST

from config.ajax import error
from config.throttle import client_ip, hit

from .forms import InquiryForm
from .services import inquiry_service


@require_POST
def submit(request):
    if hit("inquiry", client_ip(request), 10, 60 * 60):
        return error("ส่งข้อความบ่อยเกินไป กรุณาลองใหม่ภายหลัง", status=429)
    form = InquiryForm(request.POST)
    if not form.is_valid():
        return render(request, "inquiries/_form.html", {"form": form}, status=422)
    inquiry_service.create_inquiry(form)
    return render(request, "inquiries/_thanks.html")
