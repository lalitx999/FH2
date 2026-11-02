from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(autoretry_for=(SMTPException, OSError), retry_backoff=True, max_retries=3)
def send_email(subject, body, recipients):
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
