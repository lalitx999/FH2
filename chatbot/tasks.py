import logging

from celery import shared_task

from .models import ChatMessage
from .services import chat_service

logger = logging.getLogger(__name__)


@shared_task(time_limit=180)
def generate_reply_task(message_id):
    answer = ChatMessage.objects.select_related("session").get(pk=message_id)
    if answer.status != ChatMessage.Status.PENDING:
        return
    try:
        chat_service.generate_reply(answer)
    except Exception:
        # ต้องปิดสถานะเสมอ ไม่เช่นนั้นหน้าเว็บจะรอคำตอบค้าง
        logger.exception("สร้างคำตอบแชท %s ไม่สำเร็จ", message_id)
        chat_service.mark_failed(answer)
