import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError

from chatbot.models import ChatMessage, ChatSession
from chatbot.providers import rule_based
from chatbot.providers.base import ProviderError
from config.throttle import client_ip, hit

from . import knowledge_service, provider_service

logger = logging.getLogger(__name__)

SESSION_KEY = "chat_session_id"
SESSION_LIMIT = (20, 10 * 60)
IP_LIMIT = (60, 60 * 60)
HISTORY_MESSAGES = 10
PENDING_LOCK_SECONDS = 120
FAILED_REPLY = "ขออภัยครับ ระบบตอบไม่ได้ในตอนนี้ กรุณาลองใหม่ หรือติดต่อเจ้าหน้าที่"


class ChatError(Exception):
    """ข้อความใน exception นี้แสดงให้ผู้ใช้เห็นได้"""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def current_session(request):
    session_id = request.session.get(SESSION_KEY)
    return ChatSession.objects.filter(pk=session_id).first() if session_id else None


def _get_or_create_session(request):
    session = current_session(request)
    if session is None:
        session = ChatSession.objects.create(user=request.user if request.user.is_authenticated else None)
        request.session[SESSION_KEY] = str(session.pk)
    return session


def send_message(request, text):
    """บันทึกคำถาม แล้วส่งงานสร้างคำตอบให้ Celery คืน (ข้อความผู้ใช้, ข้อความผู้ช่วย)"""
    from chatbot.tasks import generate_reply_task

    text = text.strip()
    if not text:
        raise ChatError("กรุณาพิมพ์ข้อความ")
    if len(text) > settings.CHAT_MAX_MESSAGE_LENGTH:
        raise ChatError(f"ข้อความยาวได้ไม่เกิน {settings.CHAT_MAX_MESSAGE_LENGTH} ตัวอักษร")
    if hit("chat-ip", client_ip(request), *IP_LIMIT):
        raise ChatError("ส่งข้อความบ่อยเกินไป กรุณาลองใหม่ภายหลัง", status=429)

    session = _get_or_create_session(request)
    if hit("chat-session", session.pk, *SESSION_LIMIT):
        raise ChatError("ส่งข้อความบ่อยเกินไป กรุณารอสักครู่", status=429)
    lock_from = timezone.now() - timedelta(seconds=PENDING_LOCK_SECONDS)
    if session.messages.filter(status=ChatMessage.Status.PENDING, created_at__gte=lock_from).exists():
        raise ChatError("กรุณารอคำตอบก่อนหน้าสักครู่", status=429)

    with transaction.atomic():
        question = ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=text)
        answer = ChatMessage.objects.create(
            session=session, role=ChatMessage.Role.ASSISTANT, status=ChatMessage.Status.PENDING,
        )
        session.save(update_fields=["updated_at"])
    try:
        generate_reply_task.delay(answer.pk)
    except OperationalError:
        # คิวล่มยังตอบแบบไม่ใช้ LLM ได้ ไม่ต้องให้ลูกค้าเห็น error
        logger.exception("ส่งงานตอบแชทเข้าคิวไม่สำเร็จ")
        _answer_with_rules(answer, text)
    answer.refresh_from_db()
    return question, answer


def _question_for(answer):
    return answer.session.messages.filter(role=ChatMessage.Role.USER, id__lt=answer.id).order_by("-id").first()


def _history_for(answer):
    recent = answer.session.messages.filter(id__lt=answer.id, status=ChatMessage.Status.DONE).order_by("-id")
    return [{"role": m.role, "content": m.content} for m in reversed(recent[:HISTORY_MESSAGES])]


def _actions_for(query):
    if query.intent == "consign":
        return [{"label": "ฝากขายทรัพย์", "url": reverse("properties:consignment"), "icon": "fa-file-signature"}]
    if query.intent == "contact":
        return [{"label": "ติดต่อเรา", "url": reverse("pages:contact"), "icon": "fa-phone"}]
    if query.has_criteria:
        return [{"label": "ดูผลการค้นหาทั้งหมด", "url": knowledge_service.search_url(query), "icon": "fa-magnifying-glass"}]
    return []


def _finish(answer, content, provider, query, properties):
    answer.content = content
    answer.provider = provider
    answer.status = ChatMessage.Status.DONE
    answer.actions = _actions_for(query)
    answer.save(update_fields=["content", "provider", "status", "actions"])
    answer.suggestions.set(properties[:3])


def _answer_with_rules(answer, text):
    query = knowledge_service.analyze(text)
    properties = knowledge_service.find_properties(query) if query.has_criteria else []
    _finish(answer, rule_based.reply(query, properties), rule_based.NAME, query, properties)


def generate_reply(answer):
    """ลองผู้ให้บริการตามลำดับ ถ้าใช้ไม่ได้ทั้งหมดจะจบที่คำตอบตามกฎ

    การ์ดทรัพย์มาจากฐานข้อมูลเสมอ LLM จึงแนะนำทรัพย์ที่ไม่มีจริงผ่านการ์ดไม่ได้
    """
    question = _question_for(answer)
    query = knowledge_service.analyze(question.content)
    properties = knowledge_service.find_properties(query) if query.has_criteria else []
    system = knowledge_service.build_system_prompt(properties)
    messages = _history_for(answer)
    for provider in provider_service.active_providers():
        try:
            content = provider.generate(system, messages).strip()
        except ProviderError as exc:
            logger.warning("LLM ใช้ไม่ได้: %s", exc)
            continue
        if content:
            _finish(answer, content, provider.name, query, properties)
            return
    _finish(answer, rule_based.reply(query, properties), rule_based.NAME, query, properties)


def mark_failed(answer):
    answer.content = FAILED_REPLY
    answer.status = ChatMessage.Status.FAILED
    answer.save(update_fields=["content", "status"])
