import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailNotification


logger = logging.getLogger(__name__)


def _sanitized_failure(exc):
    message = " ".join(str(exc).splitlines())
    password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
    if password:
        message = message.replace(password, "[REDACTED]")
    return f"{type(exc).__name__}: {message}"[:2000]


def send_email_notification(to_email, subject, message, user=None):
    notification = EmailNotification.objects.create(
        user=user,
        to_email=to_email,
        subject=subject,
        message=message,
    )

    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        if sent_count != 1:
            raise RuntimeError("Email backend did not confirm delivery.")
    except Exception as exc:
        notification.status = EmailNotification.Status.FAILED
        notification.error_message = _sanitized_failure(exc)
        notification.save(update_fields=["status", "error_message"])
        logger.warning(
            "Email notification failed id=%s recipient=%s subject=%s status=%s",
            notification.id,
            notification.to_email,
            notification.subject,
            notification.status,
        )
        return {"success": False, "notification": notification}

    notification.status = EmailNotification.Status.SENT
    notification.sent_at = timezone.now()
    notification.error_message = None
    notification.save(update_fields=["status", "sent_at", "error_message"])
    logger.info(
        "Email notification sent id=%s recipient=%s subject=%s status=%s",
        notification.id,
        notification.to_email,
        notification.subject,
        notification.status,
    )
    return {"success": True, "notification": notification}
