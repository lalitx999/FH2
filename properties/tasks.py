import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .services import consignment_service
from .services.image_service import UploadError

logger = logging.getLogger(__name__)


@shared_task
def convert_consignment_task(consignment_id, user_id):
    user = get_user_model().objects.get(pk=user_id)
    try:
        consignment_service.convert_to_property(consignment_id, user)
    except UploadError:
        # ธุรกรรมถูกย้อนกลับแล้ว เจ้าหน้าที่กดแปลงใหม่ได้
        logger.exception("แปลงคำขอฝากขาย %s ไม่สำเร็จ", consignment_id)
