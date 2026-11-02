from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from config.ajax import error

from .models import ChatMessage
from .selectors import chat_selector as selector
from .services import chat_service


@require_POST
def send(request):
    try:
        question, answer = chat_service.send_message(request, request.POST.get("message", ""))
    except chat_service.ChatError as exc:
        return error(str(exc), status=exc.status)
    return render(request, "chatbot/_messages.html", {
        "chat_messages": [question, selector.message_for_session(question.session, answer.pk)],
    })


@require_GET
def message(request, pk):
    """ดึงคำตอบที่รออยู่ ตอบ 204 เมื่อยังไม่เสร็จ และอ่านได้เฉพาะแชทของ session นี้"""
    item = selector.message_for_session(chat_service.current_session(request), pk)
    if item is None:
        raise Http404
    if item.status == ChatMessage.Status.PENDING:
        return HttpResponse(status=204)
    return render(request, "chatbot/_messages.html", {"chat_messages": [item]})


@require_GET
def history(request):
    items = selector.history(chat_service.current_session(request))
    return render(request, "chatbot/_messages.html", {"chat_messages": items})
