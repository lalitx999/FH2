import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from kombu.exceptions import OperationalError

from .models import Property
from .services import consignment_service, map_service
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


@shared_task
def resolve_map_coordinates_task(property_id):
    link = Property.objects.filter(pk=property_id).values_list("google_maps_link", flat=True).first()
    coords = map_service.coordinates_from_short_link(link)
    if coords:
        Property.objects.filter(pk=property_id, latitude__isnull=True, longitude__isnull=True).update(
            latitude=coords[0], longitude=coords[1],
        )


def queue_map_coordinates(property_id):
    try:
        resolve_map_coordinates_task.delay(property_id)
    except OperationalError:
        # ประกาศบันทึกแล้ว คิวล่มต้องไม่ทำให้ผู้ลงเห็น error กดบันทึกอีกครั้งเพื่อลองใหม่ได้
        logger.exception("ส่งงานดึงพิกัดของประกาศ %s เข้าคิวไม่สำเร็จ", property_id)
